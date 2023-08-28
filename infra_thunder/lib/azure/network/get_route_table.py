from typing import Optional

from pulumi_azure_native import network

from ..resources import get_resourcegroup


def get_route_table(route_table_name: Optional[str] = None, resource_group_name: Optional[str] = None):
    # avoid call to get_resourcegroup if resource_group_name is set
    resource_group_name_ = resource_group_name or get_resourcegroup().name
    return network.get_route_table(
        resource_group_name=resource_group_name_,
        route_table_name=route_table_name or resource_group_name_,
    )
