from os import walk
from os.path import basename, samefile, abspath
from pathlib import Path
from typing import Optional

from pulumi import log

from infra_thunder.lib.utils import kebab_from_snake
from .lazy_module import LazyModule

_package_name = "infra_thunder"
_module_container_name = "modules"


def _get_package_path(path: Optional[Path] = Path(abspath(__file__))) -> Path:
    if samefile(path, "/"):
        raise Exception(f"module population failed: package is named something other than `{_package_name}`")
    elif basename(path) == _package_name:
        return path
    else:
        return _get_package_path(path.parent)


def _get_dirs(path: Path) -> list[str]:
    """Get all directories in ``path`` that don't start with underscore

    :param path: Path to start from
    :return: List of directories in ``path``
    """
    _, dirs, _ = next(walk(path))
    return [d for d in dirs if not d.startswith("_")]


def discover_modules() -> dict[str, dict[str, LazyModule]]:
    """Find all modules

    Assumes that the path to a module is ``infra_thunder/modules/{provider}/{module}``.

    The module folder name is converted from snake to kebab case for the nested dictionary key.

    Example::

        # thunder
        # └── modules
        #     ├── aws
        #     │   ├── s3
        #     │   └── iam_roles
        #     └── azure
        #         ├── storage
        #         └── iam

        {
            "aws": {
                "s3": LazyModule(provider='aws', name='s3'),
                "iam-roles": LazyModule(provider='aws', name='iam_roles'),
            },
            "azure: {
                "storage": LazyModule(provider='azure', name='storage'),
                "iam": LazyModule(provider='azure', name='iam'),
            },
        }

    :return: A mapping of providers to mappings of module names to lazy modules
    """
    package_path = _get_package_path()

    log.debug(f"identified package path for `{_package_name}` as `{str(package_path)}`")

    providers_path = package_path / _module_container_name

    return {
        provider: {
            kebab_from_snake(module_name): LazyModule(provider, module_name)
            for module_name in _get_dirs(providers_path / provider)
        }
        for provider in _get_dirs(providers_path)
    }
