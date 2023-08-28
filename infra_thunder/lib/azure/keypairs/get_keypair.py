from typing import Optional

from pulumi_azure_native.compute import get_ssh_public_key

from infra_thunder.lib.azure.resources import get_resourcegroup
from .helpers import get_keypair_name


def get_keypair(resource_group_name: Optional[str] = None):
    resource_group_name_ = resource_group_name or get_resourcegroup()
    return get_ssh_public_key(resource_group_name=resource_group_name_, ssh_public_key_name=get_keypair_name())
