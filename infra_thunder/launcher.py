import logging
import os

from pulumi import get_stack, log, export

from infra_thunder.lib.config import get_provider_override
from infra_thunder.module_manager import module_manager


def run_stack(provider: str, stack_name: str) -> None:
    """Invoke a module with its stack configuration

    :param provider: A provider
    :param stack_name: The stack name
    :return: None
    """

    # allow stacks to require shared modules
    provider = get_provider_override() or provider

    module = module_manager.get_module(provider, stack_name)

    log.debug(f"running module `{stack_name}`")

    exports = module.run(stack_name)

    export(stack_name, exports)


def run_active_stack(provider: str) -> None:
    """Invoke the active module with its configuration

    :param provider: A provider
    :return: None
    """
    stack = get_stack()

    log.debug(f"active stack is `{stack}`")

    run_stack(provider, stack)


# We need to configure Thunder's log level before it's imported since it creates a
# logger and does all its work on import time.
if os.getenv("THUNDER_DEBUG"):
    logging.basicConfig(level=logging.DEBUG)
    msg = "thunder logging enabled"
    log.debug(msg)
    logging.debug(msg)
