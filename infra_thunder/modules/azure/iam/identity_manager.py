from dataclasses import dataclass
from typing import Union

from pulumi import ResourceOptions, Output
from pulumi_azure_native.authorization import RoleAssignment, PrincipalType
from pulumi_azure_native.managedidentity import UserAssignedIdentity

from infra_thunder.lib.azure.iam import get_role_definition_id
from infra_thunder.lib.azure.storage import get_blob_account, get_file_account


@dataclass
class IdentityManager:
    identity: UserAssignedIdentity
    name: str

    def grant_access_to_blob_accounts(self, blob_names: list[str]) -> None:
        """Grant the contained identity access to blob-purpose storage accounts

        :param blob_names: Names of blob accounts
        :return: None
        """
        for account in blob_names:
            self._grant_access_to_blob_account(account)

    def _grant_access_to_blob_account(self, blob_name: str) -> None:
        container_id = get_blob_account(blob_name)["container_id"]
        self._create_role_assignment(f"{self.name}-{blob_name}", container_id, "Storage Blob Data Contributor")

    def grant_access_to_file_shares(self, file_names: list[str]) -> None:
        """Grant the contained identity access to file-purpose storage accounts

        :param file_names: Names of file accounts
        :return: None
        """
        for account in file_names:
            self._grant_access_to_file_account(account)

    def _grant_access_to_file_account(self, file_name: str) -> None:
        share_id = get_file_account(file_name)["share_id"]
        self._create_role_assignment(
            f"{self.name}-{file_name}",
            share_id,
            "Storage File Data SMB Share Contributor",
        )

    def _create_role_assignment(self, name: str, scope: Union[str, Output[str]], role_definition_name: str) -> None:
        RoleAssignment(
            name,
            scope=scope,
            principal_id=self.identity.principal_id,
            principal_type=PrincipalType.SERVICE_PRINCIPAL,
            role_definition_id=get_role_definition_id(role_definition_name, scope=scope),
            opts=ResourceOptions(parent=self.identity),
        )
