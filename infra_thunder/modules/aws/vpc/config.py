from dataclasses import dataclass
from typing import Optional

from pulumi import Output


@dataclass
class VPCSubnetConfig:
    availability_zone: str
    """Where should this subnet be placed?"""

    cidr_block: str
    """Subnet CIDR block (10.5.22.0/24)"""

    purpose: str
    """Purpose of this subnet (public, private, lb, dmz,...)"""
    # TODO: this should become an enum to prevent misspellings

    preferred: bool = False
    """Should single-instance services prefer this subnet?"""


@dataclass
class VPCArgs:
    supernet: str
    """
    Network CIDR that encapsulates all CIDRs in this new VPC (10.5.0.0/16)
    This supernet will become a managed prefix list used to construct security groups and VPC peering connections
    """

    cidr: str
    """The primary CIDR of this VPC"""

    secondary_cidrs: list[str]
    """Secondary CIDRs for this VPC."""

    public_subnets: list[VPCSubnetConfig]
    """List of public subnet configurations"""

    private_subnets: list[VPCSubnetConfig]
    """List of private subnet configurations"""

    domain_name: Optional[str]
    """DNS domain name for the AmazonProvidedDNS to use when resolving local names"""

    create_nat: bool = True
    """If we have private subnets, should we create NATGateway instances?"""

    create_endpoints: bool = True
    """Create VPC endpoints for AWS services like s3 to avoid public internet egress for these services"""

    allow_internal_ssh: bool = True
    """Should the internal security group allow SSH from instance to instance by default?"""


@dataclass
class VPCExports:
    vpc_id: Output[str]
    supernet: str
    cidrs: list[str]
    prefix_list: Output[str]
    peered_prefix_list: Output[str]
    default_ssh_pubkey: Output[str]
    default_ssh_privatekey: Output[str]
    private_subnets: Optional[list[Output[str]]]
    private_routes: Optional[list[Output[str]]]
    public_subnets: Optional[list[Output[str]]]
    public_routes: Optional[list[Output[str]]]
    default_security_groups: Optional[list[Output[str]]]
