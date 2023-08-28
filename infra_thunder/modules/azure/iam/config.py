from dataclasses import dataclass, field


@dataclass
class IdentityConfig:
    name: str
    """Name for the user-assigned managed identity resource"""

    blob_accounts: list[str] = field(default_factory=list)
    """Names of blob-purpose storage accounts to have access to"""

    file_accounts: list[str] = field(default_factory=list)
    """Names of fileshare-purpose storage accounts to have access to"""


@dataclass
class IAMConfig:
    identities: list[IdentityConfig]


@dataclass
class IAMExports:
    identities: list[str]
