# This file is boilerplate. Copy it to any new projects you create.
# Its' purpose is to call the launcher that exists as part of `infra_thunder`.
# From there, the appropriate module to run is extracted from the stack name.
#
# If you need to use custom stack names (for instance, a migration from stack "k8s-agents" to "k8s-agents-v2")
# you can directly call the launcher for the module you wish to use
# based off the return value of `pulumi.get_stack()`.
#
# But that's not recommended currently, and you'll be on your own :)
# - The Sign Painter
from infra_thunder.launcher import run_active_stack

run_active_stack("aws")
