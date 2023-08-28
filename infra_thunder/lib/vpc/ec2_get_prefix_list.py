from pulumi_aws import ec2

from .constants import DEFAULT_PREFIX_LIST, SUPERNET
from ..config import tag_prefix, get_sysenv


def get_prefix_list() -> ec2.AwaitableGetManagedPrefixListResult:
    """
    Get the prefix lists valid for this SysEnv.
    This is accomplished by filtering all prefix lists AWS-side.

    :return:
    """
    return ec2.get_managed_prefix_list(
        filters=[
            ec2.GetManagedPrefixListFilterArgs(
                name=f"tag:{tag_prefix}service",
                values=[DEFAULT_PREFIX_LIST],
            ),
            ec2.GetManagedPrefixListFilterArgs(
                name=f"tag:{tag_prefix}role",
                values=[SUPERNET],
            ),
            ec2.GetManagedPrefixListFilterArgs(
                name=f"tag:{tag_prefix}sysenv",
                values=[get_sysenv()],
            ),
        ]
    )


get_supernet = get_prefix_list
