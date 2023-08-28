from pulumi_azure_native import authorization

from infra_thunder.lib.utils import run_once


@run_once
def get_client_config() -> authorization.AwaitableGetClientConfigResult:
    """Access the current configuration of the native Azure provider.

    :return: Client configuration including client, subscription and tenant IDs
    """
    return authorization.get_client_config()


def get_subscription_id() -> str:
    """Get the configured subscription ID for the provider

    :return: The subscription ID
    """
    return get_client_config().subscription_id


def get_tenant_id() -> str:
    """
    Get the tenant ID for the currently logged in az cli user

    :return: The tenant ID
    """
    return get_client_config().tenant_id
