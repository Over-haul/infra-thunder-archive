"""
Transit gateway:
- get org arn
- create the TGW in the current provider
- create the RAM share
- associate the RAM share with the TGW
- share the RAM share with the org arn
- phase 1: for every aws_profile listed in the config (validating config!)
  - create provider
  - get the account id
  - look up the sysenv name and ensure it matches the config
  - add the provider/account-id/name to a list
  - look up the SUPERNET for that account and collect it into a list
- phase 2: for every aws_profile listed in the config (cartesian product of sysenv::supernet)
  - for every SUPERNET collected in phase 1, add routes to the TGW object
  - add routes to the transit account's subnets to the TGW
  - add routes in every subnet for every known supernet to the TGW
- for every SUPERNET collected in phase 1, add routes to the current provider (central routing table)

use tgw prefix list?
can't use get_tags for remote resources - must build tags manually (?)
can't use get_subnets for remote resources - must do it manually
"""
from dataclasses import dataclass
from typing import Optional

from pulumi import ResourceOptions, InvokeOptions, log
from pulumi_aws import (
    ec2,
    ram,
    organizations,
    ec2transitgateway,
    provider,
)

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import tag_prefix
from infra_thunder.lib.route_tables import get_route_tables
from infra_thunder.lib.subnets import get_all_subnets_attributes
from infra_thunder.lib.tags import get_tags, get_sysenv
from infra_thunder.lib.vpc import (
    get_vpc,
    DEFAULT_PREFIX_LIST,
    PEERED_PREFIX_LIST,
    SUPERNET,
    get_prefix_list,
    get_peered_prefix_list,
)
from .config import (
    TransitGatewayConnectionConfig,
    TransitGatewayExports,
    TransitGatewayConnectionExport,
    TransitGatewayConfig,
)


@dataclass
class RemoteAccount:
    sysenv: str
    connection_config: Optional[TransitGatewayConnectionConfig]
    provider: Optional[provider.Provider]
    profile: Optional[str]
    cidr: str
    peered_prefixlist: Optional[ec2.AwaitableGetManagedPrefixListResult]
    vpc: ec2.AwaitableGetVpcResult
    attachment: Optional[ec2transitgateway.VpcAttachment]


class TransitGateway(AWSModule):
    def __init__(self, name: str, config: TransitGatewayConfig, opts: ResourceOptions = None):
        super().__init__(name, config, opts)

        self.vpc = get_vpc()

    def build(self, config: TransitGatewayConfig) -> TransitGatewayExports:
        # create the transit gateway in the current sysenv
        tgw, tgw_deps = self._create_tgw()

        # collect account and account information
        remote_accounts: list[RemoteAccount] = []

        # discover accounts and subnets to be associated with the tgw
        for connection in config.connections:
            p = provider.Provider(
                f"{connection.sysenv}-provider",
                profile=connection.profile,
                # cross-region transit gateways are not supported.
                # if required, create two transit gateways in the same transit account and peer them together.
                region=self.region,
                opts=ResourceOptions(parent=tgw),
            )
            # get the supernet for this sysenv
            remote_sysenv_cidr = self._get_sysenv_supernet(p, connection)

            # get the peered prefixlist for this sysenv
            peered_prefixlist = self._get_sysenv_peered_prefixlist(p, connection)

            # fetch the remote vpc
            remote_vpc = self._get_sysenv_vpc(p, connection)

            # discover the primary private subnets to attach the tgw to
            primary_subnets = self._get_sysenv_primary_subnet_ids(p, connection, remote_vpc)

            # create the transit gateway attachment to the remote vpc's primary private subnets
            attachment = self._attach_tgw_to_vpc(p, connection, tgw, remote_vpc, primary_subnets, tgw_deps)

            # add a route to the supernet cidr via this tgw
            ec2transitgateway.Route(
                f"{connection.sysenv}-tgwroute",
                transit_gateway_route_table_id=tgw.association_default_route_table_id,
                transit_gateway_attachment_id=attachment,
                destination_cidr_block=remote_sysenv_cidr,
            )

            # append the account to the list of accounts
            remote_accounts.append(
                RemoteAccount(
                    sysenv=connection.sysenv,
                    connection_config=connection,
                    provider=p,
                    profile=connection.profile,
                    cidr=remote_sysenv_cidr,
                    peered_prefixlist=peered_prefixlist,
                    vpc=remote_vpc,
                    attachment=attachment,
                )
            )

        # collect the list of all known cidrs
        remote_cidrs: list[str] = []
        for account in remote_accounts:
            remote_cidrs.append(account.cidr)

        local_cidr = get_prefix_list().entries[0].cidr

        # do we have an any public subnets? if so, use those
        # this allows us to support air-gapped networks (no public subnets, no nat gateways)
        local_subnets = get_all_subnets_attributes(self.vpc.id)
        local_public_subnets = list(filter(lambda x: x.tags.get(f"{tag_prefix}role") == "public", local_subnets))
        local_private_subnets = list(filter(lambda x: x.tags.get(f"{tag_prefix}role") == "private", local_subnets))
        tgw_subnets = local_public_subnets if len(local_public_subnets) > 0 else local_private_subnets

        # attach the tgw to the transit account
        ec2transitgateway.VpcAttachment(
            "local-attachment",
            transit_gateway_id=tgw.id,
            vpc_id=get_vpc().id,
            subnet_ids=[x.id for x in tgw_subnets],
            # tags=...,  # tags
            opts=ResourceOptions(parent=self),
        )

        # for every local route table, make routes to every peered CIDR via the transit gateway
        for route_table_id in get_route_tables(vpc_id=self.vpc.id).ids:
            for peered_cidr in remote_cidrs:
                ec2.Route(
                    f"local-{route_table_id}-tgw-route-{peered_cidr}",
                    destination_cidr_block=peered_cidr,
                    transit_gateway_id=tgw.id,
                    route_table_id=route_table_id,
                    opts=ResourceOptions(parent=tgw),
                )

        # for every remote account, make routes in every remote subnet to all the known peered cidrs
        for account in remote_accounts:
            # get the list of accounts this account is allowed to peer with, and remove self (don't peer self with self!)
            peered_accounts = list(
                filter(
                    lambda x: x.sysenv in account.connection_config.allowed_sysenvs and x.sysenv != account.sysenv,
                    remote_accounts,
                )
            )

            # add the local account to the list of peered accounts
            peered_accounts.append(
                RemoteAccount(
                    sysenv=get_sysenv(),
                    connection_config=None,
                    provider=None,
                    profile=None,
                    cidr=local_cidr,
                    peered_prefixlist=None,
                    vpc=self.vpc,
                    attachment=None,
                )
            )

            log.warn(
                f"Allowed sysenvs: [{account.connection_config.allowed_sysenvs}], Peered accounts [{peered_accounts}]",
                account.provider,
            )

            # Creating a throwaway variable called cidrs for dependency chaining
            # This is a workaround for error:
            # IncorrectState: The request cannot be completed while the prefix list (pl-**) is in the current state (modify-in-progress)
            cidrs = []
            for peered_account in peered_accounts:
                cidr = ec2.ManagedPrefixListEntry(
                    f"{peered_account.sysenv}-{account.sysenv}-peered-prefixlist-entry",
                    prefix_list_id=account.peered_prefixlist.id,
                    cidr=peered_account.cidr,
                    description=f"{peered_account.sysenv} Peered SysEnv",
                    opts=ResourceOptions(
                        parent=account.provider,
                        provider=account.provider,
                        depends_on=cidrs[-1:],
                    ),
                )
                cidrs.append(cidr)

            local_peered_prefix = get_peered_prefix_list()
            ec2.ManagedPrefixListEntry(
                f"{account.sysenv}-local-peered-prefixlist-entry",
                prefix_list_id=local_peered_prefix.id,
                cidr=account.cidr,
                description=f"{account.sysenv} Peered SysEnv",
                opts=ResourceOptions(parent=self),
            )

            # add a route to the transit gateway for each CIDR in each route table
            for route_table_id in self._get_sysenv_route_tables(
                account.provider, account.connection_config, account.vpc
            ).ids:
                # add the peered accounts
                for peered_account in peered_accounts:
                    ec2.Route(
                        f"{account.connection_config.sysenv}-{route_table_id}-tgw-route-{peered_account.cidr}",
                        destination_cidr_block=peered_account.cidr,
                        transit_gateway_id=tgw.id,
                        route_table_id=route_table_id,
                        opts=ResourceOptions(parent=account.provider, provider=account.provider),
                    )

        return TransitGatewayExports(
            tgw_id=tgw.id,
            connections=[
                TransitGatewayConnectionExport(
                    sysenv=account.sysenv,
                    supernet=account.cidr,
                    allowed_sysenvs=account.connection_config.allowed_sysenvs,
                )
                for account in remote_accounts
            ],
            supernets=remote_cidrs,
        )

    def _create_tgw(self) -> (ec2transitgateway.TransitGateway, list):
        # create the tgw in the current provider
        tgw = ec2transitgateway.TransitGateway(
            "transit-gateway",
            auto_accept_shared_attachments="enable",
            description="Transit Gateway for Thunder SysEnvs",
            tags=get_tags("transit", "gateway"),
            opts=ResourceOptions(parent=self),
        )

        # create a RAM share
        share = ram.ResourceShare(
            "transit-gateway",
            allow_external_principals=False,
            tags=get_tags("transit", "gateway"),
            opts=ResourceOptions(parent=tgw),
        )
        # add the tgw to the share
        ra = ram.ResourceAssociation(
            "transit-gateway-resourceassociation",
            resource_arn=tgw.arn,
            resource_share_arn=share.arn,
            opts=ResourceOptions(parent=share),
        )
        # share the tgw with the org
        pa = ram.PrincipalAssociation(
            "transit-gateway-principalassociation",
            principal=organizations.get_organization().arn,
            resource_share_arn=share.arn,
            opts=ResourceOptions(parent=share),
        )

        return tgw, [share, ra, pa]

    def _get_sysenv_supernet(self, provider: provider.Provider, connection: TransitGatewayConnectionConfig) -> str:
        # get the managed prefix list from the resource-shared prefix list
        pl = ec2.get_managed_prefix_list(
            filters=[
                ec2.GetManagedPrefixListFilterArgs(
                    name=f"tag:{tag_prefix}service",
                    values=[DEFAULT_PREFIX_LIST],
                ),
                ec2.GetManagedPrefixListFilterArgs(
                    name=f"tag:{tag_prefix}role",
                    values=[SUPERNET],
                ),
                ec2.GetManagedPrefixListFilterArgs(
                    name=f"tag:{tag_prefix}sysenv",
                    values=[connection.sysenv],
                ),
            ],
            # InvokeOptions is for `get_*` functions.
            opts=InvokeOptions(parent=self, provider=provider),
        )
        # return just the CIDR for the sysenv
        return pl.entries[0].cidr

    def _get_sysenv_peered_prefixlist(
        self, provider: provider.Provider, connection: TransitGatewayConnectionConfig
    ) -> ec2.AwaitableGetManagedPrefixListResult:
        # get the managed peered prefix list from the resource-shared prefix list
        return ec2.get_managed_prefix_list(
            filters=[
                ec2.GetManagedPrefixListFilterArgs(
                    name=f"tag:{tag_prefix}service",
                    values=[PEERED_PREFIX_LIST],
                ),
                ec2.GetManagedPrefixListFilterArgs(
                    name=f"tag:{tag_prefix}role",
                    values=[SUPERNET],
                ),
                ec2.GetManagedPrefixListFilterArgs(
                    name=f"tag:{tag_prefix}sysenv",
                    values=[connection.sysenv],
                ),
            ],
            # InvokeOptions is for `get_*` functions.
            opts=InvokeOptions(parent=self, provider=provider),
        )

    def _get_sysenv_vpc(
        self, provider: provider.Provider, connection: TransitGatewayConnectionConfig
    ) -> ec2.AwaitableGetVpcResult:
        # get the remote sysenv vpc
        return ec2.get_vpc(
            filters=[
                ec2.GetVpcFilterArgs(name=f"tag:{tag_prefix}service", values=["VPC"]),
                ec2.GetVpcFilterArgs(name=f"tag:{tag_prefix}sysenv", values=[connection.sysenv]),
            ],
            opts=InvokeOptions(parent=self, provider=provider),
        )

    def _get_sysenv_primary_subnet_ids(
        self,
        provider: provider.Provider,
        connection: TransitGatewayConnectionConfig,
        vpc: ec2.AwaitableGetVpcResult,
    ) -> ec2.AwaitableGetSubnetIdsResult:
        # get the primary private subnets that the tgw should be attached to
        # this is necessary since a tgw is limited to one eni per availability zone - so we pick the private subnets and ignore subnets with other purposes
        # todo: what if there's no private subnets?
        return ec2.get_subnet_ids(
            vpc_id=vpc.id,
            filters=[
                ec2.GetSubnetIdsFilterArgs(name=f"tag:{tag_prefix}sysenv", values=[connection.sysenv]),
                ec2.GetSubnetIdsFilterArgs(name=f"tag:{tag_prefix}role", values=["private"]),
            ],
            opts=InvokeOptions(parent=self, provider=provider),
        )

    def _get_sysenv_route_tables(
        self,
        provider: provider.Provider,
        connection: TransitGatewayConnectionConfig,
        vpc: ec2.AwaitableGetVpcResult,
    ) -> ec2.AwaitableGetRouteTablesResult:
        return ec2.get_route_tables(
            vpc_id=vpc.id,
            filters=[
                ec2.GetSubnetIdsFilterArgs(name=f"tag:{tag_prefix}sysenv", values=[connection.sysenv]),
            ],
            opts=InvokeOptions(parent=self, provider=provider),
        )

    def _attach_tgw_to_vpc(
        self,
        provider: provider.Provider,
        connection: TransitGatewayConnectionConfig,
        tgw: ec2transitgateway.TransitGateway,
        vpc: ec2.AwaitableGetVpcResult,
        primary_subnets: ec2.AwaitableGetSubnetIdsResult,
        deps: list,
    ):
        # attach the tgw to the remote vpc
        return ec2transitgateway.VpcAttachment(
            f"{connection.sysenv}-attachment",
            transit_gateway_id=tgw.id,
            vpc_id=vpc.id,
            subnet_ids=primary_subnets.ids,
            # tags=...,  # tags
            opts=ResourceOptions(parent=provider, provider=provider, depends_on=deps),
        )
