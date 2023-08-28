from functools import lru_cache
from typing import Optional

from pulumi_azure_native import network

from infra_thunder.lib.azure.resources import get_resourcegroup
from .constants import SubnetPurpose, SubnetDelegation
from .get_vnet import get_vnet


@lru_cache
def get_subnet(
    purpose: SubnetPurpose,
    delegation: Optional[SubnetDelegation] = None,
    resource_group_name: Optional[str] = None,
    virtual_network_name: Optional[str] = None,
) -> network.AwaitableGetSubnetResult:
    # avoid calling get_resourcegroup if both resource_group_name and virtual_network_name are specified as args
    rg_name = get_resourcegroup().name if not (resource_group_name or virtual_network_name) else None

    return network.get_subnet(
        # get the resourcegroup if not specified
        resource_group_name=resource_group_name or rg_name,
        virtual_network_name=virtual_network_name or get_vnet(resource_group_name=rg_name).name,
        subnet_name=purpose.value if not delegation else f"{purpose.value}-{delegation.name}",
    )
