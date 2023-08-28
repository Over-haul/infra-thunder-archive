from typing import Optional

from pulumi_azure_native import resources

from infra_thunder.lib.config import get_sysenv


def get_resourcegroup(
    sysenv: Optional[str] = None,
) -> resources.AwaitableGetResourceGroupResult:
    return resources.get_resource_group(sysenv or get_sysenv())
