from infra_thunder.lib.stack import get_stack_output


def get_seed() -> str:
    output = get_stack_output("seed")
    return output["seed"]
