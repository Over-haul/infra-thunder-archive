from pulumi import ResourceOptions
from pulumi_azure_native.managedidentity import UserAssignedIdentity

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.tags import get_tags
from .config import IAMConfig, IAMExports, IdentityConfig
from .identity_manager import IdentityManager


class IAM(AzureModule):
    def build(self, config: IAMConfig) -> IAMExports:
        for i in config.identities:
            self._create_identity_and_assign_roles(i)

        return IAMExports(identities=[i.name for i in config.identities])

    def _create_identity_and_assign_roles(self, spec: IdentityConfig) -> None:
        """Create an identity and assign to them the roles they will require

        :param spec: Configuration for the identities
        :return: None
        """
        identity = self._create_identity(spec.name)
        manager = IdentityManager(identity=identity, name=spec.name)

        manager.grant_access_to_blob_accounts(spec.blob_accounts)
        manager.grant_access_to_file_shares(spec.file_accounts)

    def _create_identity(self, name: str) -> UserAssignedIdentity:
        """Create a user-assigned managed identity resource

        :param name: Name
        :return: An identity
        """
        return UserAssignedIdentity(
            name,
            resource_name_=name,
            **self.common_args,
            tags=get_tags(service="iam", role="identity", group=name),
            opts=ResourceOptions(parent=self),
        )
