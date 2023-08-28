from jmespath import search
from pulumi import Output

from infra_thunder.lib.stack import get_stack_output


def search_in_stack_output(stack: str, expression: str) -> Output:
    """Use a jmespath expression to query a stack output

    :param stack: Name of stack with output
    :param expression: JMESPath expression
    :return: Query result wrapped in Output
    """
    output = get_stack_output(stack)
    return output.apply(lambda v: search(expression, v))
