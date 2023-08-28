from itertools import cycle

from pulumi import ResourceOptions
from pulumi_aws import autoscaling, ec2, iam, GetAmiFilterArgs, AwaitableGetAmiResult
from pulumi_aws.ec2 import get_ami

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import get_stack
from infra_thunder.lib.iam import generate_instance_profile
from infra_thunder.lib.keypairs import get_keypair
from infra_thunder.lib.security_groups import (
    get_default_security_groups,
    SecurityGroupIngressRule,
    generate_security_group,
)
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_asg_tags, get_tags
from infra_thunder.lib.user_data import UserData
from infra_thunder.lib.vpc import get_vpc
from .config import Cluster, RabbitMQArgs


class RabbitMQ(AWSModule):
    def build(self, config: RabbitMQArgs) -> None:
        vpc = get_vpc()

        # Get the AMI
        ami = get_ami(
            owners=["amazon"],
            most_recent=True,
            filters=[
                GetAmiFilterArgs(
                    name="name",
                    values=["amzn2-ami-hvm-2.0.????????-x86_64-gp2"],
                )
            ],
        )

        subnets = get_subnets_attributes(public=False, purpose="private", vpc_id=vpc.id)
        [self._create_cluster(args=cluster, ami=ami, vpc=vpc, subnets=subnets) for cluster in config.clusters]

    def _create_cluster(
        self,
        args: Cluster,
        ami: AwaitableGetAmiResult,
        vpc: ec2.AwaitableGetVpcResult,
        subnets: list[ec2.AwaitableGetSubnetResult],
    ) -> None:
        cluster_name = f"{get_stack()}-{args.name}"

        ingress_rules = [
            SecurityGroupIngressRule(
                description="AMQP",
                from_port=5672,
                to_port=5672,
                protocol="tcp",
                allow_vpc_supernet=True,
                allow_peered_supernets=True,
            ),
            SecurityGroupIngressRule(
                description="RabbitMQ Management UI, API and rabbitmqadmin",
                from_port=15672,
                to_port=15672,
                protocol="tcp",
                allow_vpc_supernet=True,
            ),
            SecurityGroupIngressRule(
                description="any port from self",
                from_port=0,
                to_port=0,
                protocol="-1",
                self=True,
            ),
        ]

        security_group = generate_security_group(
            ingress_rules=ingress_rules,
            name=cluster_name,
            vpc_id=vpc.id,
            opts=ResourceOptions(parent=self),
        )

        _block_device_mappings = [
            ec2.LaunchTemplateBlockDeviceMappingArgs(
                device_name="/dev/xvda",
                ebs=ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                    delete_on_termination=True,
                    volume_size=args.volume_size,
                    volume_type=args.volume_type,
                ),
            )
        ]
        instance_profile, instance_role = generate_instance_profile(self, include_default=True, name=cluster_name)
        azs = cycle({subnet.availability_zone for subnet in subnets})

        for instance in range(args.count):
            az = next(azs)
            self._create_instance(
                args=args,
                ami=ami,
                block_device_mappings=_block_device_mappings,
                instance_profile=instance_profile,
                instance_role=instance_role,
                cluster_name=cluster_name,
                sg=security_group,
                subnets=[subnet for subnet in subnets if subnet.availability_zone == az],
                namespace=f"{instance}",
                vpc=vpc,
            )

    def _create_instance(
        self,
        args: Cluster,
        ami: AwaitableGetAmiResult,
        instance_profile: iam.InstanceProfile,
        instance_role: iam.Role,
        block_device_mappings: list[ec2.LaunchTemplateBlockDeviceMappingArgs],
        cluster_name: str,
        sg: ec2.SecurityGroup,
        subnets: list[ec2.AwaitableGetSubnetResult],
        namespace: str,
        vpc: ec2.AwaitableGetVpcResult,
    ) -> None:
        namespaced_cluster_name = f"{cluster_name}-{namespace}"
        eni = ec2.NetworkInterface(
            namespaced_cluster_name,
            subnet_id=subnets[0].id,
            security_groups=[sg],
            tags=get_tags(get_stack(), "eni", args.name),
            opts=ResourceOptions(parent=sg),
        )

        lt = ec2.LaunchTemplate(
            namespaced_cluster_name,
            block_device_mappings=block_device_mappings,
            iam_instance_profile=ec2.LaunchTemplateIamInstanceProfileArgs(arn=instance_profile.arn, name=get_stack()),
            ebs_optimized=True,
            key_name=get_keypair(),
            user_data=UserData(
                namespaced_cluster_name,
                include_defaults=True,
                include_cloudconfig=True,
                replacements={"cluster_name": cluster_name, "eni_id": eni.id},
                opts=ResourceOptions(parent=self, depends_on=[eni]),
            ).template,
            image_id=ami.id,
            name_prefix=get_stack(),
            instance_type=args.instance_type,
            vpc_security_group_ids=[sg.id] + get_default_security_groups(vpc_id=vpc.id).ids,
            opts=ResourceOptions(parent=instance_profile, depends_on=[eni, instance_role, sg]),
        )

        autoscaling.Group(
            namespaced_cluster_name,
            launch_template={
                "id": lt.id,
                "version": "$Latest",
            },
            tags=get_asg_tags(get_stack(), "instance", args.name),
            vpc_zone_identifiers=[subnet.id for subnet in subnets],
            suspended_processes=[
                "ReplaceUnhealthy",
            ],
            max_size=1,
            min_size=0,
            opts=ResourceOptions(parent=lt, depends_on=[instance_profile, instance_role]),
        )
