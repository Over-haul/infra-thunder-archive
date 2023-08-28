from pulumi import ResourceOptions
from pulumi_azure_native import network, compute
from pulumi_tls import PrivateKey

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.azure.keypairs.constants import DEFAULT_KEY_PAIR_NAME
from infra_thunder.lib.tags import get_tags, get_sysenv
from .config import NetworkArgs, NetworkExports, KeypairExports, SubnetPurpose


class Network(AzureModule):
    def build(self, config: NetworkArgs) -> NetworkExports:
        # TODO: DNS suffix?

        # generate default keypair
        keypair = PrivateKey(
            DEFAULT_KEY_PAIR_NAME,
            algorithm="RSA",
            rsa_bits=2048,
            opts=ResourceOptions(parent=self),
        )

        # add it to azure
        compute.SshPublicKey(
            DEFAULT_KEY_PAIR_NAME,
            ssh_public_key_name=DEFAULT_KEY_PAIR_NAME,
            public_key=keypair.public_key_openssh,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="keypair", role="default"),
            opts=ResourceOptions(parent=keypair),
        )

        # create a virtual network
        vnet = network.VirtualNetwork(
            "vnet",
            virtual_network_name=get_sysenv(),
            address_space=network.AddressSpaceArgs(address_prefixes=[config.cidr]),
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="network", role="vnet"),
            # !!important!! need to ignore `subnets` property here
            # otherwise a refresh/up op will delete subnets found at refresh time
            opts=ResourceOptions(parent=self, ignore_changes=["subnets"]),
        )

        # create a single route table for all private, non-delegated subnets
        # this route table will hold routes to all connected sysenvs (via the azure firewall)
        route_table = network.RouteTable(
            "route-table",
            route_table_name=get_sysenv(),
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="network", role="routetable"),
            # !!important!! need to ignore `routes` property here
            # otherwise a refresh/up op will delete routes found at refresh time
            opts=ResourceOptions(parent=vnet, ignore_changes=["properties.routes"]),
        )

        # public_route_table = None
        # if any(subnet_config.purpose == SubnetPurpose.PUBLIC for subnet_config in config.subnets):
        #     # Only create a public route table if we have a public subnet
        #     public_route_table = network.RouteTable(
        #         "public-route-table",
        #         route_table_name=get_sysenv(),
        #         resource_group_name=self.resourcegroup.name,
        #         tags=get_tags(service="network", role="routetable", group="public"),
        #         # !!important!! need to ignore `routes` property here
        #         # otherwise a refresh/up op will delete routes found at refresh time
        #         opts=ResourceOptions(parent=vnet, ignore_changes=["properties.routes"])
        #     )

        # do we want nat gateways?
        # this is useful for sysenvs that will only be used as transit gateways (cost savings)
        if config.create_nat:
            # create three static public ip addresses to use to help prevent source port exhaustion
            nat_ips = [
                network.PublicIPAddress(
                    f"nat-ip-{idx}",
                    public_ip_allocation_method=network.IPAllocationMethod.STATIC,
                    sku=network.PublicIPAddressSkuArgs(
                        name=network.PublicIPAddressSkuName.STANDARD,
                        tier=network.PublicIPAddressSkuTier.REGIONAL,
                    ),
                    resource_group_name=self.resourcegroup.name,
                    opts=ResourceOptions(parent=vnet),
                )
                for idx in range(1, 4)
            ]

            nat_gateway = network.NatGateway(
                "nat-gateway",
                nat_gateway_name="nat-gateway",
                sku=network.NatGatewaySkuArgs(name=network.NatGatewaySkuName.STANDARD),
                public_ip_addresses=[
                    network.SubResourceArgs(
                        id=ip.id,
                    )
                    for ip in nat_ips
                ],
                resource_group_name=self.resourcegroup.name,
                tags=get_tags(service="network", role="nat"),
                opts=ResourceOptions(parent=vnet, depends_on=nat_ips),
            )
        else:
            nat_gateway = None

        # do we want endpoints?
        # this is useful for the same reason as above
        if config.create_endpoints:
            endpoints = [
                network.ServiceEndpointPropertiesFormatArgs(
                    service="Microsoft.Storage",
                    locations=["eastus", "centralus", "westus"],
                )
            ]
        else:
            endpoints = None

        subnets = []
        for subnet_args in config.subnets:
            # name of the subnet would be `Database-PostgresFlexibleServers` if it's delegated
            subnet_name = (
                f"{subnet_args.purpose.value}-{subnet_args.delegation.name}"
                if subnet_args.delegation
                else subnet_args.purpose.value
            )

            if subnet_args.purpose == SubnetPurpose.GATEWAY or subnet_args.purpose == SubnetPurpose.FIREWALL:
                subnet_route_table = network.RouteTable(
                    f"route-table-{subnet_args.purpose.value}",
                    route_table_name=f"{get_sysenv()}-{subnet_args.purpose.value}",
                    resource_group_name=self.resourcegroup.name,
                    tags=get_tags(service="network", role="routetable"),
                    # !!important!! need to ignore `routes` property here
                    # otherwise a refresh/up op will delete routes found at refresh time
                    opts=ResourceOptions(parent=vnet, ignore_changes=["properties.routes"]),
                )

                if subnet_args.purpose == SubnetPurpose.FIREWALL:
                    network.Route(
                        "firewall-internet-route",
                        address_prefix="0.0.0.0/0",
                        route_table_name=subnet_route_table.name,
                        next_hop_type=network.RouteNextHopType.INTERNET,
                        resource_group_name=self.resourcegroup.name,
                        opts=ResourceOptions(parent=subnet_route_table),
                    )
            else:
                subnet_route_table = route_table

            # create the subnet itself
            subnet = network.Subnet(
                subnet_name,
                virtual_network_name=vnet.name,
                subnet_name=subnet_name,
                address_prefix=subnet_args.cidr_block,
                nat_gateway=network.SubResourceArgs(
                    id=nat_gateway.id,
                )
                if nat_gateway
                and (
                    subnet_args.purpose != SubnetPurpose.GATEWAY
                    and subnet_args.purpose != SubnetPurpose.PUBLIC
                    and subnet_args.purpose != SubnetPurpose.FIREWALL
                )
                else None,
                resource_group_name=self.resourcegroup.name,
                route_table=network.RouteTableArgs(id=subnet_route_table.id),
                delegations=[
                    network.DelegationArgs(
                        # Name is the simple name (PostgresFlexibleServers)
                        name=subnet_args.delegation.name,
                        # Value is the full name (Microsoft.DBforPostgreSQL/flexibleServers)
                        service_name=subnet_args.delegation.value,
                    )
                ]
                if subnet_args.delegation
                else None,
                service_endpoints=endpoints,
                # depend on the previous subnet to be created... working around a pulumi bug:
                # https://github.com/pulumi/pulumi-azure-native/issues/903
                opts=ResourceOptions(parent=vnet, depends_on=subnets[-1:]),
            )

            subnets.append(subnet)

        return NetworkExports(
            keypair=KeypairExports(
                name=DEFAULT_KEY_PAIR_NAME,
                fingerprint=keypair.public_key_fingerprint_md5,
                public_key=keypair.public_key_openssh,
                private_key=keypair.private_key_pem,
            ),
            vnet_id=vnet.id,
            route_table=route_table.id,
            subnets=subnets,
        )
