from pulumi import ComponentResource, ResourceOptions
from pulumi_aws import ssm

from infra_thunder.lib.aws.kubernetes import get_ssm_path
from infra_thunder.lib.ssm import PARAMETER_STORE_BASE
from infra_thunder.lib.tags import get_tags, get_sysenv, get_stack
from .config import K8sControllerArgs


def create_ssm_parameter(
    cls,
    dependency: ComponentResource,
    name: str,
    value: str,
    secret: bool,
    cluster_config: K8sControllerArgs,
):
    typ = "SecureString" if secret else "String"
    return ssm.Parameter(
        name,
        name=f"{PARAMETER_STORE_BASE}/{get_sysenv()}/{get_ssm_path(cluster_config.name)}/{name}",
        value=value,
        type=typ,
        tags=get_tags(service=get_stack(), role="pki", group=cluster_config.name),
        opts=ResourceOptions(parent=dependency),
    )
