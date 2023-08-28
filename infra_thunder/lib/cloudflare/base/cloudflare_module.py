from abc import ABC

from pulumi import ResourceOptions

from infra_thunder.lib.base import BaseModule, ConfigType


class CloudflareModule(BaseModule, ABC):
    """
    Base class for thunder modules using the Cloudflare provider
    """

    provider: str = "cloudflare"

    def __init__(self, name: str, config: ConfigType, opts: ResourceOptions = None):
        super().__init__(name, config, opts)
