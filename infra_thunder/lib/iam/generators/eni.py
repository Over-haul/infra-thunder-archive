from pulumi import ResourceOptions
from pulumi_aws import iam


def generate_eni_policy(cls, role: iam.Role) -> iam.RolePolicy:
    """
    Generate an inline policy that allows attachment of ENIs to an instance.

    WARNING: this policy does not (and can not) scope to the specific ENI to be attached or detached. This means that
    any instance with this policy can attach or detach any ENI from/to any instance, including itself.
    See: https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonec2.html
    (under "AttachNetworkInterface") for more information.

    :param cls: Calling class object
    :param role: The role to attach this policy to
    :return: iam.RolePolicy manage-eni
    """

    return iam.RolePolicy(
        "eni-manage",
        role=role.id,
        policy={
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:AttachNetworkInterface",
                        "ec2:DetachNetworkInterface",
                    ],
                    "Resource": "*",
                }
            ]
        },
        opts=ResourceOptions(parent=role),
    )
