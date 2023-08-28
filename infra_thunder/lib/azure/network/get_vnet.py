from typing import Optional

from pulumi_azure_native import network

from ..resources import get_resourcegroup


def get_vnet(
    resource_group_name: Optional[str] = None,
) -> network.AwaitableGetVirtualNetworkResult:
    name = resource_group_name or get_resourcegroup().name
    return network.get_virtual_network(
        virtual_network_name=name,
        resource_group_name=name,
    )
