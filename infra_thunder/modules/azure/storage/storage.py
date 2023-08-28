from pulumi import ResourceOptions
from pulumi_azure_native import storage

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.tags import get_tags
from .config import (
    StorageConfig,
    BlobStorageAccountExport,
    FileStorageAccountExport,
    StorageExports,
)


class Storage(AzureModule):
    def build(self, config: StorageConfig) -> StorageExports:
        blob_accounts = [
            self._create_blob_storage_account(
                name=account.name,
            )
            for account in config.blob_accounts
        ]

        file_accounts = [
            self._create_file_storage_account(
                name=account.name,
            )
            for account in config.file_accounts
        ]

        return StorageExports(
            blob_accounts=blob_accounts,
            file_accounts=file_accounts,
        )

    def _create_blob_storage_account(self, name: str) -> BlobStorageAccountExport:
        """Create a storage account with a blob container inside it

        :param name: Name of the storage account and the blob container
        :return: Instance of BlobStorageAccountExport
        """
        account = self._create_storage_account(name)

        container = storage.BlobContainer(
            f"{name}-container",
            container_name=name,
            account_name=account.name,
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(parent=account),
        )

        return BlobStorageAccountExport(
            name=name,
            id=account.id,
            account_name=account.name,
            container_name=name,
            container_id=container.id,
        )

    def _create_file_storage_account(self, name: str) -> FileStorageAccountExport:
        """Create a storage account with a fileshare inside it

        :param name: Name of the storage account and the fileshare
        :return: Instance of FileStorageAccountExport
        """
        account = self._create_storage_account(name)

        share = storage.FileShare(
            f"{name}-fileshare",
            share_name=name,
            account_name=account.name,
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(parent=account),
        )

        return FileStorageAccountExport(
            name=name,
            id=account.id,
            account_name=account.name,
            share_name=name,
            share_id=share.id,
        )

    def _create_storage_account(self, name: str) -> storage.StorageAccount:
        """Create a storage account

        The name of the storage account will have a hash suffixed for uniqueness.

        :param name: Pulumi name of the storage account
        :return: The storage account
        """
        return storage.StorageAccount(
            name,
            kind=storage.Kind.STORAGE_V2,
            sku=storage.SkuArgs(
                name=storage.SkuName.STANDARD_ZRS,
            ),
            access_tier=storage.AccessTier.HOT,
            is_hns_enabled=False,
            enable_nfs_v3=False,
            allow_blob_public_access=False,
            allow_shared_key_access=True,
            **self.common_args,
            tags=get_tags(service="storage", role="account", group=name),
            opts=ResourceOptions(parent=self),
        )
