from pulumi import ResourceOptions
from pulumi_aws import iam


def generate_kubernetes_eni_policy(cls, role: iam.Role) -> iam.RolePolicy:
    """
    Generate an inline policy that allows instances to attach/detach/modify/tag ENIs.

    WARNING: this policy does not (and can not) scope to the specific ENI to be attached or detached. This means that
    any instance with this policy can attach or detach any ENI from/to any instance, including itself.
    See: https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonec2.html
    (under "AttachNetworkInterface") for more information.

    :param cls: Calling class object
    :param role: The role to attach this policy to
    :return: iam.RolePolicy manage-eni
    """

    return iam.RolePolicy(
        "eni-manage-k8s",
        role=role.id,
        policy={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:AssignPrivateIpAddresses",
                        "ec2:AttachNetworkInterface",
                        "ec2:CreateNetworkInterface",
                        "ec2:DeleteNetworkInterface",
                        "ec2:DescribeInstances",
                        "ec2:DescribeInstanceTypes",
                        "ec2:DescribeTags",
                        "ec2:DescribeNetworkInterfaces",
                        "ec2:DetachNetworkInterface",
                        "ec2:ModifyNetworkInterfaceAttribute",
                        "ec2:UnassignPrivateIpAddresses",
                    ],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["ec2:CreateTags"],
                    "Resource": ["arn:aws:ec2:*:*:network-interface/*"],
                },
            ],
        },
        opts=ResourceOptions(parent=role),
    )
