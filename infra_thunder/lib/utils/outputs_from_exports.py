from dataclasses import is_dataclass
from typing import Any

from pulumi import Output, get_stack


def _map_dict(val: dict) -> dict:
    return {k: _map(v) for k, v in val.items()}


def _map(val: Any) -> Any:
    if isinstance(val, list):
        return [_map(v) for v in val]
    elif isinstance(val, dict):
        return _map_dict(val)
    elif is_dataclass(val):
        return _map_dict(val.__dict__)
    elif isinstance(val, Output):
        return val
    elif isinstance(val, type):
        raise TypeError(f"Unexpected value '{val}' of type '{type(val)}'")
    else:
        return val


def outputs_from_exports(exports: object) -> dict:
    """Generate a serializable output from a Pulumi exports object

    Recursively converts dataclasses to dict.

    Raises an exception for any non-dataclass object found.

    :param exports: A module exports object and a dataclass instance
    :return: The output for the module
    """
    return {
        get_stack(): _map(exports),
    }
