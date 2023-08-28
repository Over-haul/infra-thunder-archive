from functools import cache

from pulumi import StackReference, Output


def _get_stack_reference(stack: str) -> StackReference:
    return StackReference(f"{stack}-stack-reference", stack_name=stack)


@cache
def get_stack_output(stack: str) -> Output:
    stack_reference = _get_stack_reference(stack)
    return stack_reference.require_output(stack)
