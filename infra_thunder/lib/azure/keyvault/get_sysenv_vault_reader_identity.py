from typing import Optional

from pulumi_azure_native.managedidentity import (
    get_user_assigned_identity,
    AwaitableGetUserAssignedIdentityResult,
)

from infra_thunder.lib.azure.resources import get_resourcegroup
from .constants import VAULT_SECRETS_READER_IDENTITY


def get_sysenv_vault_reader_identity(
    resource_group_name: Optional[str] = None,
) -> AwaitableGetUserAssignedIdentityResult:
    resource_group_name_ = resource_group_name or get_resourcegroup().name

    return get_user_assigned_identity(
        resource_group_name=resource_group_name_,
        resource_name=VAULT_SECRETS_READER_IDENTITY,
    )
