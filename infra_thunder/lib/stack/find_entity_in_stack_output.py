from typing import Optional

from jmespath import search
from pulumi import Output

from .get_stack_output import get_stack_output


def find_entity_in_stack_output(stack: str, path_to_list: str, value: str, path: Optional[str] = None) -> Output[dict]:
    """Find a dictionary in a list in a stack

    Written as a convenience method for a frequent use-case.

    :param stack: Name of stack with output
    :param path_to_list: Path to the list. Use "@" for identity.
    :param value: Value of ``path`` to look for
    :param path: Path at which to find ``value`` in each element in the list. Defaults to "name".
    :return: dict wrapped in Output
    """
    output = get_stack_output(stack)

    return output.apply(lambda v: search(f"{path_to_list}[?{path or 'name'} == `{value}`] | [0]", v))
