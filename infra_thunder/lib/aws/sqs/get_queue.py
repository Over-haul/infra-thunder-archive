from pulumi import Output

from infra_thunder.lib.stack import find_entity_in_stack_output


def get_queue(name) -> Output[dict]:
    return find_entity_in_stack_output("sqs", "queues", name)
