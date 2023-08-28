from dataclasses import dataclass
from typing import Optional

from pulumi import Output
from pulumi_azure_native.network import Subnet

from infra_thunder.lib.azure.network.constants import SubnetPurpose, SubnetDelegation


@dataclass
class SubnetConfig:
    cidr_block: str
    """ Subnet CIDR block (10.5.22.0/24) """

    purpose: SubnetPurpose
    """ Purpose of this subnet (public, private, lb, dmz,...) """

    delegation: Optional[SubnetDelegation]
    """ Optionally delegate this subnet to a specific Azure service. Not all services require delegation. """


@dataclass
class NetworkArgs:
    cidr: str
    """The primary CIDR of this Network"""

    subnets: list[SubnetConfig]
    """List of subnets for this Network"""

    domain_name: Optional[str]
    """DNS domain name for the AmazonProvidedDNS to use when resolving local names"""

    create_nat: bool = True
    """If we have private subnets, should we create NAT Gateway instances?"""

    create_endpoints: bool = True
    """Create endpoints for Azure services like Azure Storage to avoid public internet egress for these services"""

    allow_internal_ssh: bool = True
    """Should the internal security group allow SSH from instance to instance by default?"""


@dataclass
class KeypairExports:
    name: str
    fingerprint: Output[str]
    public_key: Output[str]
    private_key: Output[str]


@dataclass
class NetworkExports:
    vnet_id: Output[str]
    subnets: list[Subnet]
    keypair: KeypairExports
    route_table: Output[str]
