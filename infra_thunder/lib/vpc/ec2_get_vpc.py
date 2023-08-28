from pulumi_aws import ec2

from infra_thunder.lib.config import tag_prefix
from infra_thunder.lib.tags import get_sysenv
from infra_thunder.lib.utils import run_once


@run_once
def get_vpc() -> ec2.AwaitableGetVpcResult:
    """
    Get the VPC for the current program
    :return: VPC object
    """
    return ec2.get_vpc(
        filters=[
            ec2.GetVpcFilterArgs(name=f"tag:{tag_prefix}service", values=["VPC"]),
            ec2.GetVpcFilterArgs(name=f"tag:{tag_prefix}sysenv", values=[get_sysenv()]),
        ]
    )
