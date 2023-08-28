from pulumi import Output, ResourceOptions
from pulumi_aws import iam, ebs


def generate_ebs_policy(volume: ebs.Volume):
    """
    Generate an inline policy that allows an instance to attach a volume to itself

    :param volume: ebs.Volume to allow attachment and detachment
    :return: Curried policy generator function
    """

    def curried_generate_ebs_policy(cls, role: iam.Role) -> iam.RolePolicy:
        """
        Curried (inner) function to generate the EBS policy

        :param cls: Calling class object
        :param role: The role to attach this policy to
        :return: iam.RolePolicy manage-eni
        """

        return iam.RolePolicy(
            "ebs-manage",
            role=role.id,
            policy={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Resource": "*",
                        "Action": [
                            "ec2:DescribeVolumeAttribute",
                            "ec2:DescribeVolumeStatus",
                            "ec2:DescribeVolumes",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Resource": [
                            Output.concat(
                                "arn:",
                                cls.partition,
                                ":ec2:",
                                cls.region,
                                ":",
                                cls.aws_account_id,
                                ":volume/",
                                volume.id,
                            ),
                            f"arn:{cls.partition}:ec2:{cls.region}:{cls.aws_account_id}:instance/*",
                        ],
                        "Action": ["ec2:AttachVolume", "ec2:DetachVolume"],
                    },
                ]
            },
            opts=ResourceOptions(parent=role),
        )

    return curried_generate_ebs_policy
