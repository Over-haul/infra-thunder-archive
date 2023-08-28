from typing import Optional

from pulumi_azure_native.keyvault import get_secret, AwaitableGetSecretResult

from infra_thunder.lib.azure.resources import get_resourcegroup


def get_sysenv_secret(secret_name: str, resource_group_name: Optional[str] = None) -> AwaitableGetSecretResult:
    """
    Get details about a secret from the sysenv key vault.

    Note that the details *do not* include the secret itself.

    :param resource_group_name: The sysenv or resource group
    :param secret_name: The secret name
    :return: Secret details in the form of a GetSecretResult
    """
    resource_group_name_ = resource_group_name or get_resourcegroup().name

    return get_secret(
        resource_group_name=resource_group_name_,
        vault_name=resource_group_name_,
        secret_name=secret_name,
    )
