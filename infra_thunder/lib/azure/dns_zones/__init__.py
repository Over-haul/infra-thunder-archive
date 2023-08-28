from typing import Optional

from pulumi_azure_native import network

from infra_thunder.lib.azure.resources import get_resourcegroup
from infra_thunder.lib.config import get_public_sysenv_domain


def get_sysenv_zone(
    resource_group_name: Optional[str] = None,
) -> network.AwaitableGetZoneResult:
    resource_group_name_ = resource_group_name or get_resourcegroup()
    return network.get_zone(
        zone_name=get_public_sysenv_domain(),
        resource_group_name=resource_group_name_,
    )
