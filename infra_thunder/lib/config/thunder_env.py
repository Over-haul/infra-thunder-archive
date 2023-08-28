import logging
import sys
from collections import UserDict
from pathlib import Path

import hiyapyco

logger = logging.getLogger(__name__)


class ThunderConfigException(Exception):
    def __init__(self, key):
        super().__init__(f"Missing required configuration variable '{key}'")


class HierarchicalConfig(UserDict):
    """
    HierarchicalConfig is a UserDict that automatically loads configuration from a tiered set of config files.

    This class will load `Thunder.common.yaml` from the directory where the entrypoint that calls this class, and will
    walk the filesystem upwards a configurable number of times to find other `Thunder.common.yaml` files.

    The discovered files will be merged using a YAML object merger (HiYaPyCo) that supports Jinja2 syntax.

    Typically, you won't use this class directly, and instead will

    Example usage:
        from thunder.lib.config import thunder_env

        thunder_env.get("myconfig", "somedefault")
        thunder_env.require("myotherconfig")

    """

    def __init__(self, limit=5, filename="Thunder.common.yaml"):
        """
        Create a HierarchicalConfig UserDict

        :param limit: Max parent directories to walk
        :param filename: Filename to find and merge
        """
        super().__init__()
        self.filename = filename
        configs = list(reversed(self._discover_configs(limit)))
        logger.debug("Found configs in %s", configs)
        loader = hiyapyco.load([str(path) for path in configs])

        # expose the data from the loader as our UserDict backing store
        self.data = loader

    def require(self, key: str) -> any:
        """
        Require a key from the configuration and return it. If not found, throw a `ThunderConfigException`

        :param key: Key string to require from the configuration
        :return: Object
        """
        if v := self.get(key):
            # Yes. Python has if-assignment. Boo-yah.
            return v
        else:
            raise ThunderConfigException(key)

    def _discover_configs(self, limit) -> list[Path]:
        """
        Find the path of the __main__ module that called this class, and walk upwards to find other files

        :param limit: Max parent directories to walk
        :return:
        """
        config_paths = []

        main_module = sys.modules["__main__"]
        if not hasattr(main_module, "__file__"):
            raise Exception(
                "Can't find __file__ for __main__. HINT: Don't use HierarchicalConfig from a REPL if you are."
            )

        # we now have the entrypoint to this module
        entrypoint = Path(main_module.__file__).absolute()
        logger.debug("Entrypoint: %s", entrypoint)

        # is there a config next to the entrypoint?
        local_config = entrypoint / self.filename
        if local_config.exists():
            logger.debug("Detected local config [%s]", local_config)
            config_paths.append(local_config)

        # walk up the directory tree and find any files matching the name
        limited_parents = list(entrypoint.parents)[:limit]
        for path in limited_parents:
            logger.debug("Looking in [%s] for [%s]", path, self.filename)
            maybe_config = path / self.filename
            if maybe_config.exists():
                logger.debug("Detected parent config [%s]", maybe_config)
                config_paths.append(maybe_config)

            # break at project root if using git to save a few fstat calls
            # we do this last to allow a config file to exist at the project root level, but not higher.
            if (path / ".git").is_dir():
                logger.debug("Found project root, breaking")
                break

        return config_paths


# Create our singleton object to avoid loading and merging configuration multiple times on import
thunder_env = HierarchicalConfig()
