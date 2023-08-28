from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import Type, Optional

from pulumi import log, ResourceOptions

from infra_thunder.lib.base import BaseModule, ExportsType
from infra_thunder.lib.config import get_stack_config
from infra_thunder.lib.utils import run_once


@dataclass
class LazyModule:
    """
    Wraps a thunder module.
    Accepts a path that has been identified as a thunder module.
    Defers import until ``run`` is invoked.
    """

    provider: str
    """Name of the provider"""

    name: str
    """Name of the python module"""

    @property
    @run_once
    def path(self):
        return f".modules.{self.provider}.{self.name}"

    def _find_module_in_dir(self, module_dir: ModuleType) -> Type[BaseModule]:
        # very inefficient
        for key, value in vars(module_dir).items():
            if not key.startswith("_"):
                if isinstance(value, type) and issubclass(value, BaseModule):
                    log.debug(f"found module class `{value.__name__}`")

                    return value

        raise ModuleNotFoundError(f"no subclass of `{BaseModule.__name__}` found in `{self.path}`")

    @property
    @run_once
    def Module(self) -> Type[BaseModule]:
        log.debug(f"performing first-time import for module at `thunder{self.path}`")

        module_dir = import_module(self.path, "infra_thunder")

        return self._find_module_in_dir(module_dir)

    def run(self, stack_name: str, opts: Optional[ResourceOptions] = None) -> ExportsType:
        """Invoke a thunder module with the stack configuration

        :param stack_name: Stack name
        :param opts: Optional set of ``pulumi.ResourceOptions`` to forward to ``pulumi.ComponentResource``.
        :return: None
        """
        log.debug(f"running module `{self.name}` for stack `{stack_name}`")

        config = get_stack_config(
            stack=stack_name,
            config_cls=self.Module.get_config_type(),
        )

        module = self.Module(
            name=stack_name,
            config=config,
            opts=opts,
        )

        return module.run()
