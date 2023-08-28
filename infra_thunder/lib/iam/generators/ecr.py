from pulumi import ResourceOptions
from pulumi_aws import iam


def generate_ecr_policy(cls, role: iam.Role) -> iam.RolePolicy:
    """
    Generate an inline olicy to allows pulling images from any ECR repository in this account
    :param cls: Calling class object
    :param role: The role to attach this policy to
    :return: iam.RolePolicy
    """

    return iam.RolePolicy(
        "ecr-fetch",
        role=role.id,
        policy={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:BatchGetImage",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:GetAuthorizationToken",
                    ],
                    "Resource": "*",
                }
            ],
        },
        opts=ResourceOptions(parent=role),
    )
