from pulumi import ResourceOptions
from pulumi_aws import iam

from .resource_interpolator import interpolate_resource
from .types import RolePolicy, Statement


def create_policy(cls, policy: RolePolicy, role: iam.Role) -> iam.RolePolicy:
    """
    Create an inline policy for a given RolePolicy and Role
    :param cls: Calling class to interpolate from
    :param policy:
    :param role:
    :return: iam.RolePolicy
    """
    return iam.RolePolicy(
        policy.name,
        policy={"Statement": list([_generate_statement(cls, statement) for statement in policy.statements])},
        role=role.id,
        opts=ResourceOptions(parent=role),
    )


def _generate_statement(cls, statement: Statement) -> dict:
    return {
        "Effect": statement.Effect,
        "Resource": list([interpolate_resource(cls, resource) for resource in statement.Resource]),
        "Action": statement.Action,
    }
