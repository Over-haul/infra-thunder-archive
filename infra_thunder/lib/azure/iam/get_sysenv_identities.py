from typing import Optional

from infra_thunder.lib.azure.keyvault import get_sysenv_vault_reader_identity
from infra_thunder.lib.azure.resources import get_resourcegroup


def get_sysenv_identities(resource_group_name: Optional[str] = None) -> dict[str, dict]:
    resource_group_name_ = resource_group_name or get_resourcegroup().name
    vault_identity = get_sysenv_vault_reader_identity(resource_group_name=resource_group_name_)

    return {
        vault_identity.id: {},
    }
