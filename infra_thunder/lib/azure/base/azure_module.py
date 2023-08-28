from abc import ABC

from pulumi import ResourceOptions

from infra_thunder.lib.azure.resources import get_resourcegroup
from infra_thunder.lib.base import BaseModule, ConfigType


class AzureModule(BaseModule, ABC):
    """
    Base class for thunder modules using the Azure provider
    """

    provider: str = "azure"

    def __init__(self, name: str, config: ConfigType, opts: ResourceOptions = None):
        super().__init__(name, config, opts)

        # set the resourcegroup default
        self.resourcegroup = get_resourcegroup()

        # set the region default by looking at the resource group default
        # TODO: this kinda conflicts with tags/core.py, since it wants `azure-native:location` to be set too
        self.location = self.resourcegroup.location

        # common arguments can be used on most azure resources
        self.common_args = {
            "resource_group_name": self.resourcegroup.name,
            "location": self.location,
        }

    def build_resource_id(
        self,
        resource_provider_namespace: str,
        parent_resource_type: str,
        parent_resource_name: str,
        resource_type: str = "",
        resource_name: str = "",
    ):
        # /subscriptions/subid/resourceGroups/rg1/providers/Microsoft.Network/loadBalancers/lb/backendAddressPools/be-lb
        # the replace lets someone only pass a parent resource type and name
        # and get the lower level object without the double // at the end
        return f"{self.resourcegroup.id}/providers/{resource_provider_namespace}/{parent_resource_type}/{parent_resource_name}/{resource_type}/{resource_name}".replace(
            "//", ""
        )
