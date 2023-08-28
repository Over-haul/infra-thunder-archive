from typing import Optional

from pulumi_aws import ec2

from ..config import tag_prefix, get_sysenv
from ..vpc import get_vpc


def get_subnets_attributes(
    public: bool, purpose: Optional[str] = None, vpc_id: Optional[str] = None
) -> list[ec2.AwaitableGetSubnetResult]:
    """
    Get a list of subnets and its attributes
    :param public: Does this subnet receive a public IP
    :param purpose: The purpose of the subnet to retrieve
    :param vpc_id: VPC ID to search
    :return: List of subnets and their attributes
    """
    filters = [ec2.GetSubnetIdsFilterArgs(name=f"tag:{tag_prefix}sysenv", values=[get_sysenv()])]
    if purpose:
        filters.append(ec2.GetSubnetIdsFilterArgs(name=f"tag:{tag_prefix}role", values=[purpose]))
    ids = ec2.get_subnet_ids(vpc_id=vpc_id or get_vpc().id, filters=filters).ids
    subnets = [get_subnet_attributes(subnet_id=subnet, vpc_id=vpc_id or get_vpc().id) for subnet in ids]
    return [subnet for subnet in subnets if subnet.map_public_ip_on_launch is public]


def get_all_subnets_attributes(
    vpc_id: Optional[str] = None,
) -> list[ec2.AwaitableGetSubnetResult]:
    """
    Get all subnets in this SysEnv
    :param vpc_id: VPC ID to search
    :return: List of subnets and their attributes
    """
    ids = ec2.get_subnet_ids(
        vpc_id=vpc_id or get_vpc().id,
        filters=[ec2.GetSubnetIdsFilterArgs(name=f"tag:{tag_prefix}sysenv", values=[get_sysenv()])],
    ).ids
    return [get_subnet_attributes(subnet_id=subnet, vpc_id=vpc_id or get_vpc().id) for subnet in ids]


def get_subnet_attributes(subnet_id: str, vpc_id: Optional[str]) -> ec2.AwaitableGetSubnetResult:
    """
    Get the attributes for a given Subnet ID
    :param subnet_id: Subnet ID to search
    :param vpc_id: VPC ID to search
    :return: subnet attributes
    """
    return ec2.get_subnet(vpc_id=vpc_id or get_vpc().id, id=subnet_id)
