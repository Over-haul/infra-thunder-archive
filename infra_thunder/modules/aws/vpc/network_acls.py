from pulumi import ResourceOptions
from pulumi_aws import ec2

from infra_thunder.lib.tags import get_tags


def setup_network_acls(vpc: ec2.Vpc, subnets: list[ec2.Subnet]):
    """
    Create the 'main' Network ACL for all subnets
    :param vpc: VPC object to create NACLs for
    :param subnets: List of ec2.Subnets to appliy this new NACL to
    :return: None
    """
    ec2.NetworkAcl(
        "main",
        ingress=[
            ec2.NetworkAclIngressArgs(
                rule_no=100,
                protocol="-1",
                action="allow",
                cidr_block="0.0.0.0/0",
                from_port=0,
                to_port=0,
            )
        ],
        egress=[
            ec2.NetworkAclEgressArgs(
                rule_no=100,
                protocol="-1",
                action="allow",
                cidr_block="0.0.0.0/0",
                from_port=0,
                to_port=0,
            )
        ],
        subnet_ids=[subnet.id for subnet in subnets],
        vpc_id=vpc.id,
        tags=get_tags("NetworkACL", "main"),
        opts=ResourceOptions(parent=vpc, depends_on=subnets),
    )
