from pulumi import Config
from pulumi_aws import GetAmiFilterArgs, GetAmiResult
from pulumi_aws.ec2 import get_ami as ec2_get_ami

from ..config import thunder_env


def get_ami(name_prefix: str) -> GetAmiResult:
    """
    Retrieve an AMI ID by name prefix
    Allows overriding by specifying an ID or name prefix in the stack configuration

    This function also allows specifying an `ami_owner` account ID as part of `Thunder.common.yaml`

    Example `Pulumi.mystack.yaml`::

        config:
          aws:region: us-west-2

          ami:id_override: ami-1cb3def8 # or...
          ami:name_prefix_override: "my-ami"
          mystack:someconfig: "my config value"

    :param name_prefix: The prefix of the AMI name to fetch
    :return: GetAmiResult
    """

    ami_config = Config("ami")
    id_override = ami_config.get("id_override")
    prefix = ami_config.get("name_prefix_override") or name_prefix

    return ec2_get_ami(
        owners=[thunder_env.get("ami_owner", "self")],
        most_recent=True,
        filters=[
            GetAmiFilterArgs(
                name="image-id",
                values=[id_override],
            )
            if id_override
            else GetAmiFilterArgs(
                name="name",
                values=[f"{prefix}*"],
            )
        ],
    )
