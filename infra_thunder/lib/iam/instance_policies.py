from typing import Callable, Optional, Any

from pulumi import ResourceOptions
from pulumi_aws import iam

from infra_thunder.lib.ssm import PARAMETER_STORE_BASE
from infra_thunder.lib.tags import get_sysenv, get_stack

policy_generator = Callable[[Any, iam.Role], iam.RolePolicy]
"""
A `policy_generator` is a callable like::

def generate_my_policy(cls, role: iam.Role) -> iam.RolePolicy:
    return iam.RolePolicy("my_role", role=role.id, policy={}, opts=ResourceOptions(parent=role))

"""


def generate_instance_profile(
    cls,
    name: str,
    include_default: bool = True,
    *,
    policy_generators: Optional[set[policy_generator]] = None,
    opts: Optional[ResourceOptions] = None,
) -> (iam.InstanceProfile, iam.Role):
    """
    Generate an instance role, and instance profile. Optionally includes a default set of policies
    on the role that allow the instance to describe the environment it exists in.

    As a library author, the library may wish to provide "pre-baked" policies that a template author can use in their
    templates easily. In this case, the template author would use `policy_generators=` to reference the generators
    the library author provides in their library.

    Example::


        ebs_volume = ebs.Volume(
            ...
        )

        instance_profile, instance_role = thunder.lib.iam.generate_instance_profile(
            self,
            include_default=True,
            policy_generators={
                thunder.lib.iam.generate_eni_policy,
                thunder.lib.iam.generate_ebs_policy(ebs_volume)
            }
        )

        instance = pulumi_aws.ec2.Instance(
            ...,
            iam_instance_profile=instance_profile.arn
        )

    In the above example, the `generate_ebs_policy` function takes arguments and returns a curried function that scopes
    the generated role to apply to only the named volume.

    Similarly, as a template author, writing generators can be tedious especially if you wish to attach a simple inline
    policy to an instance role.
    In this case, the author could use the simpler form.

    Example:
        ```
        instance_profile, instance_role = thunder.lib.iam.generate_instance_profile(
            self,
            include_default=True
        )

        pulumi_aws.iam.RolePolicy(
            "my-inline-policy",
            role=instance_role.id,
            policy={...}
        )
        ```

    :param cls: Calling class object
    :param include_default: Include default policies (see ``generate_default_instancepolicy()``)
    :param policy_generators: List of role generators. This argument must be specified by name.
    :param name: namespace for when a template will contain multiple roles.
    :param opts: ResourceOptions for dependencies
    :return: iam.InstanceProfile instance-profile, iam.Role instance-role
    """
    # TODO: figure out how to pass ResourceOpts into here(?)

    # default instance role that the instance has access to without needing to call AssumeRole
    role = iam.Role(
        name,
        assume_role_policy={
            "Version": "2008-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": ["ec2.amazonaws.com"]},
                    "Action": ["sts:AssumeRole"],
                }
            ],
        },
        path="/",
        opts=opts,
    )

    if include_default:
        # Include the default instance policy
        _generate_default_ec2_policy(cls, role)
        _generate_default_ssm_policy(cls, role)

    if policy_generators:
        for generator in policy_generators:
            # Call each policy generator
            generator(cls, role)

    profile = iam.InstanceProfile(name, path="/", role=role.name, opts=opts)

    return profile, role


def _generate_default_ssm_policy(cls, role: iam.Role) -> iam.RolePolicy:
    """
    Generate a default inline policy that allows the instance to retrieve secrets from AWS SSM

    Grants access to:
        ssm:GetParameter
        ssm:GetParameters
        ssm:GetParametersByPath

    Scoped to:
        - `parameter/{PARAMETER_STORE_BASE}/{sysenv}/common/*`
          Secrets common to the entire SysEnv
        - `parameter/{PARAMETER_STORE_BASE}/{sysenv}/{stack}/{group}/*
          Secrets for the stack and specific group within the stack (group will be 'main' if no group specified)

    This policy generator is marked private to avoid accidentally calling the policy generator with
    `include_default=True` and this generator listed explicitly, which would result in generating duplicate policies.

    :param cls: The calling class object
    :param role: The role to attach this policy to
    :return: iam.RolePolicy instance-policy
    """

    return iam.RolePolicy(
        "ssm-default",
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
                        f"arn:{cls.partition}:ssm:{cls.region}:{cls.aws_account_id}:parameter{PARAMETER_STORE_BASE}/{get_sysenv()}/common/*",
                        f"arn:{cls.partition}:ssm:{cls.region}:{cls.aws_account_id}:parameter{PARAMETER_STORE_BASE}/{get_sysenv()}/{get_stack()}/main/*",
                    ],
                }
            ]
        },
        opts=ResourceOptions(parent=role),
    )


def _generate_default_ec2_policy(cls, role: iam.Role) -> iam.RolePolicy:
    """
    Generate a default inline policy that allows the instance to describe it's surroundings.

    Grants access to:
        ec2:DescribeTags
        ec2:DescribeDhcpOptions
        ec2:DescribeInstances
        ec2:DescribeNetworkInterfaces
        ec2:DescribeRegions
        ec2:DescribeVpcs

    This policy generator is marked private to avoid accidentally calling the policy generator with
    `include_default=True` and this generator listed explicitly, which would result in generating duplicate policies.

    :param cls: The calling class object
    :param role: The role to attach this policy to
    :return: iam.RolePolicy instance-policy
    """

    return iam.RolePolicy(
        "ec2-default",
        role=role.id,
        policy={
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:DescribeTags",
                        "ec2:DescribeDhcpOptions",
                        "ec2:DescribeInstances",
                        "ec2:DescribeNetworkInterfaces",
                        "ec2:DescribeRegions",
                        "ec2:DescribeVpcs",
                        "autoscaling:Describe*",
                        "autoscaling:CompleteLifecycleAction",
                    ],
                    "Resource": "*",
                }
            ]
        },
        opts=ResourceOptions(parent=role),
    )
