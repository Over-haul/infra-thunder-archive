from dataclasses import dataclass, field

from pulumi import Output


@dataclass
class StorageAccountArgs:
    name: str
    """
    The name of the storage account within the specified resource group.
    Storage account names must be between 3 and 24 characters in length and use numbers and lower-case letters only.
    Pulumi will append a hash to the name to ensure it is unique.
    """


@dataclass
class StorageConfig:
    blob_accounts: list[StorageAccountArgs] = field(default_factory=list)
    """Storage accounts intended for blob storage"""

    file_accounts: list[StorageAccountArgs] = field(default_factory=list)
    """Storage accounts intended for file storage"""


@dataclass
class BlobStorageAccountExport:
    name: str

    id: Output[str]

    account_name: Output[str]

    container_name: str

    container_id: Output[str]


@dataclass
class FileStorageAccountExport:
    name: str

    id: Output[str]

    account_name: Output[str]

    share_name: str

    share_id: Output[str]


@dataclass
class StorageExports:
    blob_accounts: list[BlobStorageAccountExport]

    file_accounts: list[FileStorageAccountExport]
