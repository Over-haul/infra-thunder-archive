from abc import ABC

from infra_thunder.lib.base import BaseModule


class SharedModule(BaseModule, ABC):
    """
    Base class for shared thunder modules
    """

    provider: str = "shared"
