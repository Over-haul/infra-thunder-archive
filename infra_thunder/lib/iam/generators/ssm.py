from pulumi import ResourceOptions
from pulumi_aws import iam

from infra_thunder.lib.ssm import PARAMETER_STORE_BASE
from infra_thunder.lib.tags import get_sysenv


def generate_ssm_policy(paths: list[str]):
    """
    Generate an inline policy that allows the instance to retrieve secrets from a specific path in AWS SSM.
    This allows access to a custom SSM path, scoped to the sysenv.

        Grants access to:
            ssm:GetParameter
            ssm:GetParameters
            ssm:GetParametersByPath

    :param paths: Paths to the SSM parameters, located under `PARAMETER_STORE_BASE/{sysenv_name}/`
    :return:
    """

    def curried_generate_ssm_policy(cls, role: iam.Role) -> iam.RolePolicy:
        """
        Curried (inner) function that returns the SSM policy

        :param cls: The calling class object
        :param role: The role to attach this policy to
        :return: iam.RolePolicy instance-policy
        """

        return iam.RolePolicy(
            "ssm-path",
            role=role.id,
            policy={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ssm:GetParameter",
                            "ssm:GetParameters",
                            "ssm:GetParametersByPath",
                        ],
                        "Resource": [
                            f"arn:{cls.partition}:ssm:{cls.region}:{cls.aws_account_id}:parameter{PARAMETER_STORE_BASE}/{get_sysenv()}/{path}"
                            for path in paths
                        ],
                    }
                ]
            },
            opts=ResourceOptions(parent=role),
        )

    return curried_generate_ssm_policy
