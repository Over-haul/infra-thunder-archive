from pulumi import ResourceOptions
from pulumi_aws import ssm

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.ssm import PARAMETER_STORE_COMMON
from infra_thunder.lib.tags import get_stack, get_tags
from .config import SSMArgs, SSMExports


class SSM(AWSModule):
    def build(self, config: SSMArgs) -> SSMExports:
        for param_name, param_value in config.parameters.items():
            ssm.Parameter(
                f"{param_name}",
                name=f"{PARAMETER_STORE_COMMON}/{param_name}",
                value=param_value,
                type=ssm.ParameterType.SECURE_STRING,
                tags=get_tags(service=get_stack(), role="common_params"),
                opts=ResourceOptions(parent=self),
            )

        return SSMExports(
            parameter_names=list(config.parameters.keys()),
        )
