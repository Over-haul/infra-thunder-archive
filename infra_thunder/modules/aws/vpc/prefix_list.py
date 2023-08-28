from pulumi import ResourceOptions
from pulumi_aws import ec2, ram
from pulumi_aws.organizations.get_organization import (
    get_organization,
)  # workaround for a pulumi_aws issue

from infra_thunder.lib.tags import get_tags, get_sysenv
from infra_thunder.lib.vpc.constants import (
    DEFAULT_PREFIX_LIST,
    PEERED_PREFIX_LIST,
    SUPERNET,
)


def setup_prefix_list(supernet: str, vpc: ec2.Vpc) -> (ec2.ManagedPrefixList, ec2.ManagedPrefixList):
    """
    Creates the managed prefix list for the supernet of this VPC

    :param supernet: The supernet to register as the prefix
    :return:
    """
    # create the supernet prefix list
    pl = ec2.ManagedPrefixList(
        "default-supernet-prefixlist",
        address_family="IPv4",
        entries=[
            ec2.ManagedPrefixListEntryArgs(
                cidr=supernet,
                description="VPC supernet",
            )
        ],
        max_entries=1,
        tags=get_tags(DEFAULT_PREFIX_LIST, SUPERNET),
        opts=ResourceOptions(parent=vpc),
    )

    # create the peered subnets prefix list
    peered_pl = ec2.ManagedPrefixList(
        "peered-supernets-prefixlist",
        address_family="IPv4",
        entries=[],
        max_entries=20,
        tags=get_tags(PEERED_PREFIX_LIST, SUPERNET),
        # Important! We must ignore the entries list here, as the TransitGateway Thunder module
        # manages the entries on this list. We only create this list here.
        opts=ResourceOptions(parent=vpc, ignore_changes=["entries"]),
    )

    # create a RAM share
    share = ram.ResourceShare(
        f"{get_sysenv()}-supernet",
        allow_external_principals=False,
        tags=get_tags(DEFAULT_PREFIX_LIST, SUPERNET),
        opts=ResourceOptions(parent=pl),
    )
    # add the prefixlist to the share
    ram.ResourceAssociation(
        f"{get_sysenv()}-pl-resourceassociation",
        resource_arn=pl.arn,
        resource_share_arn=share.arn,
        opts=ResourceOptions(parent=share),
    )
    # share the prefixlist with the org
    ram.PrincipalAssociation(
        f"{get_sysenv()}-pl-principalassociation",
        principal=get_organization().arn,
        resource_share_arn=share.arn,
        opts=ResourceOptions(parent=share),
    )

    return pl, peered_pl
