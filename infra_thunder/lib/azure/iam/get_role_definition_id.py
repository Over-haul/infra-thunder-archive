from functools import lru_cache
from typing import Optional, Union

from azure.core.credentials import AccessToken
from azure.mgmt.authorization import AuthorizationManagementClient
from pulumi import Output
from pulumi_azure_native import authorization

from infra_thunder.lib.azure.client import get_subscription_id
from infra_thunder.lib.utils import run_once


class _TokenCredential:
    def __init__(self, token):
        self.token = token

    def get_token(self, *args, **kwargs) -> AccessToken:
        # noinspection PyArgumentList
        return AccessToken(token=self.token, expires_on=-1)


@run_once
def _get_auth_manager_client() -> AuthorizationManagementClient:
    client_token = authorization.get_client_token()
    return AuthorizationManagementClient(_TokenCredential(client_token.token), get_subscription_id())


@lru_cache
def get_role_definition_id(name: str, scope: Optional[Union[str, Output[str]]] = None) -> Output[str]:
    """Get an Azure role definition ID by name

    List of built-in role def: https://docs.microsoft.com/en-us/azure/role-based-access-control/built-in-roles

    Understanding Azure RBAC scopes: https://docs.microsoft.com/en-us/azure/role-based-access-control/scope-overview

    Examples of valid scopes are:
    "/subscriptions/0b1f6471-1bf0-4dda-aec3-111122223333",
    "/subscriptions/0b1f6471-1bf0-4dda-aec3-111122223333/resourceGroups/myGroup", or
    "/subscriptions/0b1f6471-1bf0-4dda-aec3-111122223333/resourceGroups/myGroup/providers/Microsoft.Compute/virtualMachines/myVM"

    :param name: Role definition name like "Key Vault Secrets User"
    :param scope: Scope at which the role assignment or definition applies to. Defaults to "/"
    :return: ID of the named role definition
    """
    filter_ = f"roleName eq '{name}'"
    client = _get_auth_manager_client()

    def _get_role_definition_id(optional_scope: Optional[str] = None) -> str:
        scope_ = optional_scope or "/"
        role_iterator = client.role_definitions.list(scope=scope_, filter=filter_)

        try:
            role = next(role_iterator).id
        except Exception:
            raise Exception(f"role '{name}' not found at scope '{scope_}'")

        return role

    if scope:
        return Output.from_input(scope).apply(_get_role_definition_id)
    else:
        return Output.from_input(_get_role_definition_id())
