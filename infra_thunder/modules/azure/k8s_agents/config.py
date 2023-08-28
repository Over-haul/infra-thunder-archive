from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NodeGroup:
    name: str
    """Name of the NodeGroup"""

    count: int
    """How many nodes to launch in this NodeGroup"""

    instance_type: str = "Standard_D4_v3"
    """Type of the instances launched in this NodeGroup"""

    rootfs_size_gb: int = 20
    """Size of the agent rootfs in GB"""

    dockervol_size_gb: int = 20
    """Size of the docker volume in GB"""

    include_default_gateway: bool = True
    """Attach to the default gateway backend address pool"""

    extra_gateways: list[str] = field(default_factory=list)

    # labels: list[str] = field(default_factory=list)
    # """Labels to apply to nodes in this NodeGroup"""

    # dockervol_type: str = "gp2"
    # """Type of EBS volume for the dockervol (gp2, st1,...)"""


@dataclass
class SSLConfig:
    key_vault_name: str
    """Name of Key Vault that holds the SSL Cert"""

    key_vault_resource_group: str
    """Resource group of the key vault"""

    key_vault_secret_name: str
    """Secret name for certificate in the vault"""


@dataclass
class GatewayConfig:
    name: str

    ssl_config: SSLConfig


@dataclass
class SysenvGatewayConfig:
    ssl_config: SSLConfig


@dataclass
class K8sAgentsConfig:
    node_groups: list[NodeGroup]
    """List of NodeGroups"""

    gateway: SysenvGatewayConfig
    """Default Application Gateway for agents"""

    extra_gateways: Optional[list[GatewayConfig]] = field(default_factory=list)


@dataclass
class GatewayExports:
    name: str

    backend_address_pool_name: str


@dataclass
class K8sAgentsExports:
    node_groups: list[str]

    gateway: GatewayExports

    extra_gateways: Optional[list[GatewayExports]] = field(default_factory=list)
