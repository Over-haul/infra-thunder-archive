from dataclasses import dataclass

from pulumi_aws import ec2

from .config import VPCSubnetConfig


@dataclass
class SubnetAndConfig:
    """
    Simple dataclass to help reduce the amount of `zip(subnets, subnet_configs)` that are present in the codebase.
    This allows us to keep the subnet configuration object alongside the created subnet for future reference.
    """

    config: VPCSubnetConfig
    subnet: ec2.Subnet
