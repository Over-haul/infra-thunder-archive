from typing import Optional

from pulumi import Input
from pulumi_aws import ec2

from ..config import tag_prefix, get_sysenv
from ..vpc import get_vpc


def get_route_tables(
    vpc_id: Optional[str] = None,
    purpose: Optional[str] = None,
    availability_zones: Optional[list[Input[str]]] = None,
) -> ec2.AwaitableGetRouteTablesResult:
    """
    Get a list of route tables matching the given filters
    :param vpc_id: VPC ID to search
    :param purpose: The purpose of the route table to retrieve
    :param availability_zones: Availability zone to filter for
    :return: List of route tables matching the given filters
    """
    filters = [ec2.GetSubnetIdsFilterArgs(name=f"tag:{tag_prefix}sysenv", values=[get_sysenv()])]

    if purpose:
        filters.append(ec2.GetSubnetIdsFilterArgs(name=f"tag:{tag_prefix}role", values=[purpose]))

    if availability_zones:
        filters.append(ec2.GetSubnetIdsFilterArgs(name=f"tag:{tag_prefix}group", values=availability_zones))

    return ec2.get_route_tables(vpc_id=vpc_id or get_vpc().id, filters=filters)
