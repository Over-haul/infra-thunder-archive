from pulumi import ComponentResource, ResourceOptions, Output, get_stack
from pulumi_azure_native import keyvault

from infra_thunder.lib.azure.client import get_tenant_id
from infra_thunder.lib.tags import get_tags


def create_vault(
    cls, dependency: ComponentResource, vault_name: str, secrets: dict[str, Output[str]]
) -> (keyvault.Vault, dict[str, Output[str]]):
    # Create a vault and add secrets to it
    vault = keyvault.Vault(
        vault_name,
        properties=keyvault.VaultPropertiesArgs(
            tenant_id=get_tenant_id(),
            enable_rbac_authorization=True,
            sku=keyvault.SkuArgs(
                name=keyvault.SkuName.STANDARD,
                family=keyvault.SkuFamily.A,
            ),
        ),
        **cls.common_args,
        tags=get_tags(service=get_stack(), role="vault", group=vault_name),
        opts=ResourceOptions(parent=dependency),
    )

    secret_uris = {}
    for secret_name, secret_value in secrets.items():
        secret = keyvault.Secret(
            secret_name,
            secret_name=secret_name,
            properties=keyvault.SecretPropertiesArgs(
                value=secret_value,
            ),
            vault_name=vault.name,
            resource_group_name=cls.resourcegroup.name,
            tags=get_tags(service=get_stack(), role="secret", group=vault_name),
            opts=ResourceOptions(parent=vault),
        )
        secret_uris[secret_name] = secret.properties.secret_uri

    return vault, secret_uris
