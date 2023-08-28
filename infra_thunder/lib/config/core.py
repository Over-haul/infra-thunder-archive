from typing import Optional
from pulumi import Config, get_stack, get_project

from infra_thunder.lib.utils import run_once
from .thunder_env import thunder_env

aws_config = Config("aws")
azure_config = Config("azure-native")
thunder_config = Config("thunder")

tag_namespace = thunder_env.get("tag_namespace", "thunder")
"""Resources created using the tagging libraries Thunder provides use this to prefix the standard tags.
   This differs from the `CONFIG_NAMESPACE`, as this is used for the actual resources, not the Pulumi config itself.
"""

tag_prefix = f"{tag_namespace}{thunder_env.get('tag_separator', ':')}"

stack = get_stack()
project = get_project()

team = thunder_env.require("team")


def get_provider_and_region():
    """
    Retrieve the provider and region for this program
    :return: (provider, region)
    """
    aws_region = aws_config.get("region")
    azure_region = azure_config.get("location")

    if aws_region:
        return "aws", aws_region
    elif azure_region:
        return "az", azure_region
    else:
        raise Exception("Unknown provider!")


def get_purpose():
    return thunder_env.require("purpose")


def get_phase():
    return thunder_env.require("phase")


@run_once
def get_sysenv():
    """
    Returns the SysEnv name for this program
    SysEnvs are named `{namespace}-{provider}-{region}-{purpose}-{phase}`.

    An example SysEnv name is `co-aws-us-west-2-sandbox-dev`

    Can be overridden by setting `sysenv` in your Thunder.common.yaml

    :return: SysEnv name
    """
    config_sysenv = thunder_env.get("sysenv")

    namespace = thunder_env.require("namespace")
    provider, region = get_provider_and_region()

    if config_sysenv:
        return config_sysenv
    elif all([namespace, provider, region]):
        return f"{namespace}-{provider}-{region}-{get_purpose()}-{get_phase()}"
    else:
        raise AttributeError(
            f"namespace[{namespace}], region[{region}], provider[{provider}], purpose[{get_purpose()}], "
            f"or phase[{get_phase()}] not set on project, can't build sysenv value"
        )


def get_internal_sysenv_domain():
    """
    Returns the internal sysenv domain for the sysenv

    Example: co-aws-us-west-2-sandbox-dev.thunder

    :return:
    """
    return f"{get_sysenv()}.{tag_namespace}"


def get_public_base_domain() -> str:
    """
    Returns the base domain used for creating all sysenvs under it
    :return:
    """
    return thunder_env.require("public_base_domain")


def get_public_sysenv_domain():
    """
    Returns the specific domain used by this current sysenv
    :return:
    """
    return f"{get_sysenv()}.{get_public_base_domain()}"


def get_provider_override() -> Optional[str]:
    """
    Retrieve the provider override for the current module (`thunder:provider: myprovider`)

    :return: bool
    """
    return thunder_config.get("provider")
