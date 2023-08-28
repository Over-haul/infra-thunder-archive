from functools import lru_cache
from typing import Optional

from pulumi_azure_native.keyvault import get_vault, AwaitableGetVaultResult

from infra_thunder.lib.azure.resources import get_resourcegroup


@lru_cache
def get_sysenv_vault(
    resource_group_name: Optional[str] = None,
) -> AwaitableGetVaultResult:
    """
    Get details about the sysenv key vault.

    :param resource_group_name: The sysenv or resource group
    :return: Vault details in the form of a GetVaultResult
    """
    resource_group_name_ = resource_group_name or get_resourcegroup().name

    return get_vault(resource_group_name=resource_group_name_, vault_name=resource_group_name_)
