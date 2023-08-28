from pulumi import ResourceOptions, Output
from pulumi_aws import iam

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.aws.kinesis import get_stream
from infra_thunder.lib.aws.sqs import get_queue
from infra_thunder.lib.s3 import get_bucket
from infra_thunder.lib.iam import create_policy
from infra_thunder.lib.iam.generators import assumable_roles
from .config import RoleConfig, Role, RoleExports


class IAMRoles(AWSModule):
    def build(self, config: RoleConfig) -> RoleExports:
        if config.path and config.path != assumable_roles.ASSUMABLE_ROLES_PATH:
            raise NotImplementedError("Setting role path not supported yet.")

        path = f"{assumable_roles.ASSUMABLE_ROLES_PATH}/"

        # Create the roles themselves
        roles = [self._create_role(path, definition) for definition in config.roles]

        # Register them as complete in the UI
        return RoleExports(path=path, roles=[role.arn for role in roles])

    def _create_role(self, path: str, role_definition: Role) -> iam.Role:
        """
        Create an assumable role with attached policies

        :param role_definition:
        :return:
        """
        role = iam.Role(
            role_definition.name,
            description=role_definition.description or f"Thunder-generated role [{role_definition.name}]",
            assume_role_policy={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            # TODO: this might need to be scoped to the instance role!
                            # "AWS": [GetAtt(self.instance_role, 'Arn')]
                            "AWS": f"arn:aws:iam::{self.aws_account_id}:root"
                        },
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            path=path,
            opts=ResourceOptions(parent=self),
        )

        for bucket in role_definition.buckets:
            self._create_bucket_policy(bucket, role, role_definition.name)

        for stream in role_definition.kinesis:
            self._create_kinesis_policy(stream, role, role_definition.name)

        for queue in role_definition.sqs:
            self._create_sqs_policy(queue, role, role_definition.name)

        for policy in role_definition.policies:
            create_policy(self, policy, role)

        return role

    def _create_bucket_policy(self, bucket: str, role: iam.Role, role_name: str) -> iam.RolePolicy:
        """
        Create an inline policy for a given S3 bucket
        :param bucket:
        :return:
        """
        bucket_name = get_bucket(bucket)["bucket"]
        bucket_policy_name = bucket.replace("/", "_").replace("*", "star")
        return iam.RolePolicy(
            f"{role_name}-s3-{bucket_policy_name}",
            policy={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:ListBucket"],
                        "Resource": Output.concat(f"arn:{self.partition}:s3:::", bucket_name),
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["s3:Put*", "s3:Get*", "s3:DeleteObject"],
                        "Resource": Output.concat(f"arn:{self.partition}:s3:::", bucket_name, "/*"),
                    },
                ]
            },
            role=role.id,
            opts=ResourceOptions(parent=role),
        )

    def _create_kinesis_policy(self, name: str, role: iam.Role, role_name: str) -> iam.RolePolicy:
        """
        Create an inline policy for a given kinesis stream
        """
        arn = get_stream(name)["arn"]

        return iam.RolePolicy(
            f"{role_name}-kinesis-{name}",
            policy={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            f"kinesis:{a}"
                            for a in (
                                # https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonkinesis.html
                                "Describe*",
                                "Get*",
                                "List*",
                                "Put*",
                                "RegisterStreamConsumer",
                                "DeregisterStreamConsumer",
                                "SubscribeToShard",
                                "SplitShard",
                                "MergeShards",
                                "UpdateShardCount",
                            )
                        ],
                        "Resource": [
                            arn,
                            Output.concat(arn, "/*"),
                        ],
                    },
                ]
            },
            role=role.id,
            opts=ResourceOptions(parent=role),
        )

    def _create_sqs_policy(self, name: str, role: iam.Role, role_name: str) -> iam.RolePolicy:
        """
        Create an inline policy for a given sqs queue
        """
        arn = get_queue(name)["arn"]

        return iam.RolePolicy(
            f"{role_name}-sqs-{name}",
            policy={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            f"sqs:{a}"
                            for a in (
                                # https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonsqs.html
                                "Get*",
                                "List*",
                                "Send*",
                                "ReceiveMessage",
                                "ChangeMessageVisibility",
                                "ChangeMessageVisibilityBatch",
                                "DeleteMessage",
                                "DeleteMessageBatch",
                                "PurgeQueue",
                            )
                        ],
                        "Resource": [arn],
                    },
                ]
            },
            role=role.id,
            opts=ResourceOptions(parent=role),
        )
