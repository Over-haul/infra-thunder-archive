from pulumi import ResourceOptions
from pulumi_aws import autoscaling, ec2, iam, GetAmiFilterArgs, AwaitableGetAmiResult
from pulumi_aws.ec2 import get_ami

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import get_sysenv, get_stack
from infra_thunder.lib.iam import generate_instance_profile
from infra_thunder.lib.keypairs import get_keypair
from infra_thunder.lib.security_groups import (
    get_default_security_groups,
    SecurityGroupIngressRule,
    generate_security_group,
)
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_asg_tags
from infra_thunder.lib.user_data import UserData
from infra_thunder.lib.vpc import get_vpc
from .config import Cluster, ElasticSearchArgs


class ElasticSearch(AWSModule):
    def build(self, config: ElasticSearchArgs) -> None:
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
        s3_backup_bucket = config.s3_backup_bucket
        [
            self._create_cluster(
                args=cluster,
                ami=ami,
                vpc=vpc,
                subnets=subnets,
                s3_backup_bucket=s3_backup_bucket,
            )
            for cluster in config.clusters
        ]

    def _create_cluster(
        self,
        args: Cluster,
        ami: AwaitableGetAmiResult,
        vpc: ec2.AwaitableGetVpcResult,
        subnets: list[ec2.AwaitableGetSubnetResult],
        s3_backup_bucket: str,
    ) -> None:
        cluster_name = f"{get_stack()}-{args.name}"
        env_cluster_name = f"{get_sysenv()}-{cluster_name}"

        ingress_rules = [
            SecurityGroupIngressRule(
                description="ES REST",
                from_port=9200,
                to_port=9200,
                protocol="tcp",
                allow_vpc_supernet=True,
                allow_peered_supernets=True,
            ),
            SecurityGroupIngressRule(
                description="ES Inter-Node",
                from_port=9300,
                to_port=9300,
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

        if args.data_volume_type:
            _block_device_mappings.append(
                ec2.LaunchTemplateBlockDeviceMappingArgs(
                    device_name="/dev/sdf",
                    ebs=ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                        delete_on_termination=True,
                        volume_size=args.data_volume_size,
                        volume_type=args.data_volume_type,
                    ),
                )
            )

        instance_profile, instance_role = generate_instance_profile(self, include_default=True, name=cluster_name)

        iam.RolePolicy(
            f"{cluster_name}-s3-backups",
            role=instance_role.id,
            policy={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:ListBucket",
                            "s3:GetBucketLocation",
                            "s3:ListBucketMultipartUploads",
                            "s3:ListBucketVersions",
                        ],
                        "Resource": [f"arn:{self.partition}:s3:::{s3_backup_bucket}"],
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:AbortMultipartUpload",
                            "s3:ListMultipartUploadParts",
                        ],
                        "Resource": [f"arn:{self.partition}:s3:::{s3_backup_bucket}/elasticsearch/{args.name}/*"],
                    },
                ]
            },
            opts=ResourceOptions(parent=instance_role),
        )

        lt = ec2.LaunchTemplate(
            cluster_name,
            block_device_mappings=_block_device_mappings,
            iam_instance_profile=ec2.LaunchTemplateIamInstanceProfileArgs(arn=instance_profile.arn, name=get_stack()),
            ebs_optimized=True,
            key_name=get_keypair(),
            user_data=UserData(
                cluster_name,
                include_defaults=True,
                include_cloudconfig=True,
                replacements={
                    "cluster_name": cluster_name,
                    "env_cluster_name": env_cluster_name,
                },
                opts=ResourceOptions(parent=self),
            ).template,
            image_id=ami.id,
            name_prefix=get_stack(),
            instance_type=args.instance_type,
            vpc_security_group_ids=[security_group.id] + get_default_security_groups(vpc_id=vpc.id).ids,
            opts=ResourceOptions(parent=instance_profile, depends_on=[instance_role, security_group]),
        )

        autoscaling.Group(
            cluster_name,
            launch_template={
                "id": lt.id,
                "version": "$Latest",
            },
            tags=get_asg_tags(get_stack(), "instance", args.name),
            vpc_zone_identifiers=[subnet.id for subnet in subnets],
            suspended_processes=[
                "ReplaceUnhealthy",
            ],
            max_size=args.count,
            min_size=args.count * 2,
            opts=ResourceOptions(parent=lt, depends_on=[instance_profile, instance_role]),
        )
