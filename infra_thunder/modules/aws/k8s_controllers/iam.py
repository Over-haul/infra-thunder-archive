from pulumi import ResourceOptions, ComponentResource
from pulumi_aws import iam, sqs

from infra_thunder.lib.aws.kubernetes import get_ssm_path
from infra_thunder.lib.iam import (
    generate_instance_profile,
    generate_kubernetes_eni_policy,
    generate_ecr_policy,
    generate_assumable_role_policy,
    generate_ssm_policy,
    generate_s3_policy,
)
from infra_thunder.lib.iam.generators.assumable_roles import ASSUMABLE_ROLES_PATH
from infra_thunder.lib.tags import get_stack
from .config import K8sControllerArgs
from .types import IamAuthenticatorRole


def create_controller_role(
    cls,
    dependency: ComponentResource,
    backups_bucket,
    cluster_config: K8sControllerArgs,
) -> (iam.Role, list[iam.RolePolicyAttachment]):
    """
    Generate the role for the controllers that allows them to:
        - Access SSM parameters in {stack_name}/{cluster_name}
        - Backup to S3 under {backups_bucket}/{cluster_name}/*
        - Create/tag/delete/update ENIs
        - Assume service roles
        - Access ECR for containers

    :param cls: Parent class object
    :param dependency: Dependency object
    :param backups_bucket: S3 backups bucket name
    :param cluster_config: Kubernetes Cluster Configuration
    :return: iam.Role
    """
    instance_profile, instance_role = generate_instance_profile(
        cls,
        include_default=True,
        policy_generators={
            generate_ssm_policy([f"{get_ssm_path(cluster_config.name)}/*"]),
            generate_s3_policy(backups_bucket, f"{cluster_config.name}/*"),
            generate_kubernetes_eni_policy,
            generate_assumable_role_policy,
            generate_ecr_policy,
        },
        name=f"{get_stack()}-{cluster_config.name}",
        opts=ResourceOptions(parent=dependency),
    )
    iam.RolePolicy(
        "s3-e2d-backups-lifecycle-put",
        role=instance_role.id,
        policy={
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:PutLifecycleConfiguration"],
                    "Resource": [f"arn:{cls.partition}:s3:::{backups_bucket}"],
                },
            ]
        },
        opts=ResourceOptions(parent=instance_role),
    )

    return instance_profile, instance_role


def create_user_role(
    cls,
    dependency: ComponentResource,
    role: IamAuthenticatorRole,
    cluster_config: K8sControllerArgs,
) -> (IamAuthenticatorRole, iam.Role):
    """
    Create a role to be used for administration of the cluster.
    This role will be assumed by AWS IAM Authenticator to generate a token to access kubeapi

    :return: iam.Role
    """
    return role, iam.Role(
        f"k8s-user-{cluster_config.name}-{role.name}",
        assume_role_policy={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:{cls.partition}:iam::{cls.aws_account_id}:root"},
                    "Action": "sts:AssumeRole",
                }
            ],
        },
        opts=ResourceOptions(parent=dependency),
    )


def create_node_bootstrap_role(cls, dependency: ComponentResource, cluster_config: K8sControllerArgs) -> iam.Role:
    """
    Create a role to be used for bootstrapping nodes into the cluster.
    This role will be assumed by nodes when they wish to join the cluster

    :return: iam.Role
    """
    return iam.Role(
        f"k8s-node-{cluster_config.name}-bootstrap",
        assume_role_policy={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:{cls.partition}:iam::{cls.aws_account_id}:root"},
                    "Action": "sts:AssumeRole",
                }
            ],
        },
        opts=ResourceOptions(parent=dependency),
    )


def create_ebs_controller_role(cls, dependency: ComponentResource, cluster_config: K8sControllerArgs) -> iam.Role:
    """

    :return: iam.Role
    """
    role = iam.Role(
        f"k8s-node-{cluster_config.name}-ebs-controller",
        assume_role_policy={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:{cls.partition}:iam::{cls.aws_account_id}:root"},
                    "Action": "sts:AssumeRole",
                }
            ],
        },
        path=f"{ASSUMABLE_ROLES_PATH}/",
        opts=ResourceOptions(parent=dependency),
    )

    iam.RolePolicy(
        "ebs-manage-k8s",
        role=role.id,
        policy={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:AttachVolume",
                        "ec2:CreateSnapshot",
                        "ec2:CreateTags",
                        "ec2:CreateVolume",
                        "ec2:DeleteSnapshot",
                        "ec2:DeleteTags",
                        "ec2:DeleteVolume",
                        "ec2:DescribeAvailabilityZones",
                        "ec2:DescribeInstances",
                        "ec2:DescribeSnapshots",
                        "ec2:DescribeTags",
                        "ec2:DescribeVolumes",
                        "ec2:DescribeVolumesModifications",
                        "ec2:DetachVolume",
                        "ec2:ModifyVolume",
                    ],
                    "Resource": "*",
                },
            ],
        },
        opts=ResourceOptions(parent=role),
    )

    return role


def create_node_termination_handler_role(
    cls, dependency: ComponentResource, cluster_config: K8sControllerArgs, node_termination_handler_queue: sqs.Queue
) -> iam.Role:
    """

    :return: iam.Role
    """
    role_name = f"k8s-node-{cluster_config.name}-termination-handler"[0:56]
    role = iam.Role(
        role_name,
        assume_role_policy={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:{cls.partition}:iam::{cls.aws_account_id}:root"},
                    "Action": "sts:AssumeRole",
                }
            ],
        },
        path=f"{ASSUMABLE_ROLES_PATH}/",
        opts=ResourceOptions(parent=dependency),
    )

    iam.RolePolicy(
        f"{cluster_config.name}-aws-node-termination-handler-policy",
        policy={
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "autoscaling:CompleteLifecycleAction",
                        "autoscaling:DescribeAutoScalingInstances",
                        "autoscaling:DescribeTags",
                        "ec2:DescribeInstances",
                    ],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "sqs:DeleteMessage",
                        "sqs:ReceiveMessage",
                    ],
                    "Resource": node_termination_handler_queue.arn,
                },
            ]
        },
        role=role.id,
        opts=ResourceOptions(parent=role),
    )

    return role


def create_cluster_autoscaler_role(cls, dependency: ComponentResource, cluster_config: K8sControllerArgs) -> iam.Role:
    role = iam.Role(
        f"k8s-node-{cluster_config.name}-autoscaler",
        assume_role_policy={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:{cls.partition}:iam::{cls.aws_account_id}:root"},
                    "Action": "sts:AssumeRole",
                }
            ],
        },
        path=f"{ASSUMABLE_ROLES_PATH}/",
        opts=ResourceOptions(parent=dependency),
    )

    iam.RolePolicy(
        f"k8s-node-{cluster_config.name}-cluster-autoscaler",
        role=role.id,
        policy={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "autoscaling:DescribeAutoScalingGroups",
                        "autoscaling:DescribeAutoScalingInstances",
                        "autoscaling:DescribeLaunchConfigurations",
                        "autoscaling:DescribeTags",
                        "autoscaling:SetDesiredCapacity",
                        "autoscaling:TerminateInstanceInAutoScalingGroup",
                        "ec2:DescribeInstanceTypes",
                        "ec2:DescribeLaunchTemplates",
                        "ec2:DescribeLaunchTemplateVersions",
                    ],
                    "Resource": "*",
                },
            ],
        },
        opts=ResourceOptions(parent=role),
    )

    return role
