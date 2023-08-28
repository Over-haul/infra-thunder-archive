from typing import Optional

from pulumi_aws import ec2

from .constants import DEFAULT_SECURITY_GROUP
from ..config import tag_prefix
from ..vpc import get_vpc


def get_default_security_groups(
    vpc_id: Optional[str] = None,
) -> ec2.AwaitableGetSecurityGroupsResult:
    """
    Get the default security groups for this SysEnv.
    This is accomplished by filtering all security groups AWS-side.

    :param vpc_id: Optional VPC ID to search, leave empty to auto detect
    :return:
    """
    return ec2.get_security_groups(
        filters=[
            ec2.GetSecurityGroupsFilterArgs(
                name=f"tag:{tag_prefix}service",
                values=[DEFAULT_SECURITY_GROUP],
            ),
            ec2.GetSecurityGroupsFilterArgs(
                name="vpc-id",
                values=[vpc_id or get_vpc().id],
            ),
        ]
    )
