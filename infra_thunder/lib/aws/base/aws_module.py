from abc import ABC

from pulumi import ResourceOptions, Config
from pulumi_aws import get_caller_identity, get_partition

from infra_thunder.lib.base import BaseModule, ConfigType


class AWSModule(BaseModule, ABC):
    """
    Base class for thunder modules using the AWS provider
    """

    provider: str = "aws"

    def __init__(self, name: str, config: ConfigType, opts: ResourceOptions = None):
        super().__init__(name, config, opts)

        self.region = Config(self.provider).require("region")
        self.aws_account_id = get_caller_identity().account_id
        self.partition = get_partition().partition
