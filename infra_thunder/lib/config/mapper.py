import json
from enum import Enum
from typing import Type, Any

from dacite import from_dict, Config
from pulumi import log, runtime

from infra_thunder.lib.base import ConfigType


def _parse_args_value(value: Any) -> Any:
    """Parse and return json values if valid json, else return original value

    :param value: A potential json string
    :return: Parsed json object or raw arg
    """
    try:
        return json.loads(value)
    except json.decoder.JSONDecodeError:
        return value


def get_raw_stack_config(stack: str) -> dict:
    """Pull stack config from Pulumi internals, clean it and return in dict form

    This method may break when upgrading the ``pulumi`` python dependency.

    :param stack: Name of the stack
    :return: dict
    """
    stack_prefix = stack + ":"

    config = {
        k.removeprefix(stack_prefix): _parse_args_value(v)
        for k, v in runtime.config.CONFIG.items()
        if k.startswith(stack_prefix)
    }

    log.debug(f"config dict for stack `{stack}` is {config}")

    return config


def get_stack_config(stack: str, config_cls: Type[ConfigType]) -> ConfigType:
    """Get a stack config in dataclass form

    Uses `dacite <https://github.com/konradhalas/dacite>`_ to map dict to dataclass.

    :param stack: Name of the stack
    :param config_cls: The dataclass for the config
    :return: The stack config expressed in the module's config dataclass
    """
    raw_config = get_raw_stack_config(stack)

    config = from_dict(
        data_class=config_cls,
        data=raw_config,
        config=Config(
            cast=[Enum],
            strict=True,
        ),
    )

    log.debug(f"config for stack `{stack}` is {config}")

    return config
