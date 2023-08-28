from functools import partial

from pulumi import ResourceOptions
from pulumi_azure_native import authorization, managedidentity
from pulumi_azure_native.keyvault import (
    Vault,
    Secret,
    VaultPropertiesArgs,
    SkuArgs,
    SkuName,
    SkuFamily,
    SecretPropertiesArgs,
)

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.azure.client import get_tenant_id
from infra_thunder.lib.azure.iam import get_role_definition_id
from infra_thunder.lib.azure.keyvault import constants
from infra_thunder.lib.config import get_sysenv
from infra_thunder.lib.tags import get_tags
from .config import KeyVaultConfig, KeyVaultExports


class KeyVault(AzureModule):
    def build(self, config: KeyVaultConfig) -> KeyVaultExports:
        sysenv_vault = self._create_sysenv_vault()
        self._create_secrets(sysenv_vault, get_sysenv(), config.secrets)

        return KeyVaultExports(
            secrets=list(config.secrets.keys()),
        )

    def _create_sysenv_vault(self) -> Vault:
        """
        Create the sysenv vault and create an identity that can access it.

        :return: The sysenv key vault
        """
        vault = self._create_vault(get_sysenv())

        identity = managedidentity.UserAssignedIdentity(
            constants.VAULT_SECRETS_READER_IDENTITY,
            resource_name_=constants.VAULT_SECRETS_READER_IDENTITY,
            **self.common_args,
            tags=get_tags(service="keyvault", role="identity", group=get_sysenv()),
            opts=ResourceOptions(parent=vault),
        )

        authorization.RoleAssignment(
            f"{constants.VAULT_SECRETS_READER_IDENTITY}-role-assignment",
            scope=vault.id,
            principal_id=identity.principal_id,
            principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
            role_definition_id=get_role_definition_id("Key Vault Secrets User", scope=vault.id),
            opts=ResourceOptions(parent=identity),
        )

        return vault

    def _create_vault(self, name: str) -> Vault:
        """
        Create a key vault.

        :param name: The name of the vault
        :return: A key vault
        """
        return Vault(
            name,
            vault_name=name,
            properties=VaultPropertiesArgs(
                tenant_id=get_tenant_id(),
                enable_rbac_authorization=True,
                sku=SkuArgs(
                    name=SkuName.STANDARD,
                    family=SkuFamily.A,
                ),
            ),
            **self.common_args,
            tags=get_tags(service="keyvault", role="vault", group=name),
            opts=ResourceOptions(parent=self),
        )

    def _create_secrets(self, vault: Vault, vault_name: str, secrets: dict[str, str]) -> list[Secret]:
        """
        Create secrets in a key vault.

        :param vault: The Pulumi vault resource
        :param vault_name: The name of the vault
        :param secrets: Secrets in dict form, secret name to value
        :return:
        """
        create_sysenv_secret = partial(self._create_secret, vault=vault, vault_name=vault_name)
        return [create_sysenv_secret(secret_name=k, value=v) for k, v in secrets.items()]

    def _create_secret(self, vault: Vault, vault_name: str, secret_name: str, value: str) -> Secret:
        """
        Create a secret in a key vault.

        We need both ``vault`` and ``vault_name``.
        ``vault_name`` gives us a resolved vault name to use as a prefix to create a
        well-differentiated pulumi resource name while the ``vault`` resource allows us to correctly set parent-child
        relationships.

        :param vault: The Pulumi vault resource
        :param vault_name: The name of the vault
        :param secret_name: The secret name
        :param value: The secret value
        :return: A secret
        """
        return Secret(
            f"{vault_name}-{secret_name}",
            secret_name=secret_name,
            properties=SecretPropertiesArgs(
                value=value,
            ),
            vault_name=vault_name,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="keyvault", role="secret", group=vault_name),
            opts=ResourceOptions(parent=vault),
        )
