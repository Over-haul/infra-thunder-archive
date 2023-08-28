from pulumi import log

from .discover_modules import discover_modules
from .lazy_module import LazyModule


class _ModuleManager:
    """Stores and hands out thunder modules."""

    def __init__(self):
        """Initialize the module manager

        The ``modules`` instance attribute would look like::

            {
                "shared":
                    "seed": LazyModule(provider='shared', name='seed'),
                },
                "aws": {
                    "s3": LazyModule(provider='aws', name='s3'),
                    "ssm": LazyModule(provider='aws', name='ssm'),
                },
                "azure": {
                    "dns": LazyModule(provider='azure', name='dns'),
                }
            }
        """
        self.modules = discover_modules()

        log.debug(f"discovered modules `{self.modules}`")

    def get_module(self, provider: str, module_name: str) -> LazyModule:
        """Returns the module's class without calling it.

        :param provider: Provider name
        :param module_name: Module name
        :return: A LazyModule
        """
        try:
            lazy_module = self.modules[provider][module_name]

            log.debug(f"accessing module `{lazy_module}`")

            return lazy_module
        except KeyError:
            raise ModuleNotFoundError(f"module `{module_name}` was not found under provider `{provider}`")

    def get_provider_modules(self, provider: str) -> dict[str, LazyModule]:
        """Helper function used to return the dictionary of known Thunder modules for a specified provider

        :param provider: Provider name
        :return: The collection of modules for a provider
        """
        return self.modules[provider]

    def get_all_modules(self) -> dict[str, dict[str, LazyModule]]:
        """Helper function used to return the dictionary of known Thunder modules

        :return: The full collection of modules
        """
        return self.modules


module_manager = _ModuleManager()
