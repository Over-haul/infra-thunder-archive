from abc import ABC, abstractmethod
from typing import Type, get_type_hints

from pulumi import ComponentResource, ResourceOptions

from infra_thunder.lib.base.types import ConfigType, ExportsType
from infra_thunder.lib.utils import outputs_from_exports, run_once


class BaseModule(ComponentResource, ABC):
    """
    The base class for a thunder module
    """

    @property
    @abstractmethod
    def provider(self):
        """Name of the provider"""

    def __init__(self, name: str, config: ConfigType, opts: ResourceOptions = None):
        super().__init__(
            f"pkg:thunder:{self.provider}:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )

        self._config = config

    @classmethod
    @run_once
    def get_config_type(cls) -> Type[ConfigType]:
        try:
            return get_type_hints(cls.build)["config"]
        except KeyError:
            raise TypeError(f"module `build` method does not have a type hint for the `config` param")

    def run(self) -> ExportsType:
        """Execute the module

        :return: An exports object
        """
        exports = self.build(self._config)

        self.register_outputs(outputs_from_exports(exports))

        return exports

    @abstractmethod
    def build(self, config: get_config_type) -> ExportsType:
        """Create cloud resources

        :return: An exports object
        """
