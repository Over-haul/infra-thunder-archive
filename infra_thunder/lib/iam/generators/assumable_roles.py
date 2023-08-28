from pulumi import ResourceOptions
from pulumi_aws import iam

ASSUMABLE_ROLES_NAMESPACE = "services"
"""Namespace for all assumable roles to exist under. Use this for specifying resources in an ARN."""

ASSUMABLE_ROLES_PATH = f"/{ASSUMABLE_ROLES_NAMESPACE}"
"""Path-formatted namespace for all assumable roles. Use this for any policies requiring a `path` parameter."""


def generate_assumable_role_policy(cls, role: iam.Role) -> iam.RolePolicy:
    """
    Generate an inline policy that allows this instance to assume any roles scoped to the assumable roles namespace.

    This is used for allowing an instance that hosts containers to forcibly assume a role on behalf of a container,
    and impersonate the AWS Metadata API to provide the scoped credentials only.

    See ``iam_roles/`` for more information about how these roles are generated. This function is only concerned with
    generating the policy that allows an instance to assume a role generated there.

    :param cls: Calling class object
    :param role: Role to attach this policy to directly
    :return: iam.Policy assumable-roles-policy
    """

    return iam.RolePolicy(
        "assumable-roles",
        role=role.id,
        # description=f"Allow instance to assume roles scoped to path {ASSUMABLE_ROLES_PATH}",
        policy={
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["sts:AssumeRole"],
                    "Resource": [f"arn:{cls.partition}:iam::{cls.aws_account_id}:role/{ASSUMABLE_ROLES_NAMESPACE}/*"],
                }
            ]
        },
        opts=ResourceOptions(parent=role),
    )
