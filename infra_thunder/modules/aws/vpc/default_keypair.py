from pulumi import ResourceOptions, Resource
from pulumi_aws import ec2
from pulumi_tls import private_key

from infra_thunder.lib.keypairs import DEFAULT_KEY_PAIR_NAME
from infra_thunder.lib.tags import get_tags


def setup_default_keypair(dependency: Resource):
    """
    Create the default keypair for this SysEnv as part of the VPC

    :param dependency: Dependency Resource to parent these objects to
    """
    keypair = private_key.PrivateKey(
        "default-ec2-keypair",
        algorithm="RSA",
        rsa_bits=2048,
        opts=ResourceOptions(parent=dependency),
    )
    ec2.KeyPair(
        "default",
        key_name=DEFAULT_KEY_PAIR_NAME,
        public_key=keypair.public_key_openssh,
        tags=get_tags("keypair", DEFAULT_KEY_PAIR_NAME),
        opts=ResourceOptions(parent=keypair),
    )
    return keypair
