from pulumi import ResourceOptions
from pulumi_aws import ec2

from infra_thunder.lib.security_groups.constants import DEFAULT_SECURITY_GROUP
from infra_thunder.lib.tags import get_tags, get_sysenv
from .config import VPCArgs


def setup_security_groups(
    vpc: ec2.Vpc,
    prefix_list: ec2.ManagedPrefixList,
    peered_prefix_list: ec2.ManagedPrefixList,
    vpc_config: VPCArgs,
) -> list[ec2.SecurityGroup]:
    # Accumulate security groups here
    security_groups = []

    # Add default ping security group
    security_groups.append(
        ec2.SecurityGroup(
            f"{DEFAULT_SECURITY_GROUP}-ping",
            description=f"Default ping VPC security group for {get_sysenv()}",
            vpc_id=vpc.id,
            ingress=[
                ec2.SecurityGroupIngressArgs(
                    description="Allow ICMP ping from all instances in this supernet and any peered supernets",
                    from_port=-1,
                    to_port=-1,
                    protocol="icmp",
                    prefix_list_ids=[prefix_list.id, peered_prefix_list.id],
                )
            ],
            egress=[
                ec2.SecurityGroupEgressArgs(
                    description="Allow egress to anywhere",
                    from_port=0,
                    to_port=0,
                    protocol="-1",
                    cidr_blocks=["0.0.0.0/0"],
                )
            ],
            tags=get_tags(DEFAULT_SECURITY_GROUP, "Ping"),
            opts=ResourceOptions(parent=vpc),
        )
    )

    # Add internal instance to instance SSH security group
    if vpc_config.allow_internal_ssh:
        security_groups.append(
            ec2.SecurityGroup(
                f"{DEFAULT_SECURITY_GROUP}-ssh",
                description=f"Allow SSH to any instance in {get_sysenv()}",
                vpc_id=vpc.id,
                ingress=[
                    ec2.SecurityGroupIngressArgs(
                        description="Allow SSH to all instances from instances in this supernet",
                        from_port=22,
                        to_port=22,
                        protocol="tcp",
                        prefix_list_ids=[prefix_list.id],
                    )
                ],
                tags=get_tags(DEFAULT_SECURITY_GROUP, "SSH"),
                opts=ResourceOptions(parent=vpc),
            )
        )

    return security_groups
