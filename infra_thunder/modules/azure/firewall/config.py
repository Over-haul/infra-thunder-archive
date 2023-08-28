from dataclasses import dataclass

from pulumi import Output


@dataclass
class FirewallConnectionConfig:
    sysenv: str
    """What is the SysEnv name to operate against?"""

    allowed_sysenvs: list[str]
    """Which SysEnvs should be allowed to connect to this SysEnv?"""


@dataclass
class FirewallRemoteSysEnvConfig:
    sysenv: str
    """ SysEnv name """

    cidr: str
    """ CIDR of the remote SysEnv """


@dataclass
class FirewallRemoteConnectionConfig:
    name: str
    """ Remote connection name """

    ipsec_peers: list[str]
    """ IP address of the remote peer """

    ipsec_psk: str
    """ Secret PSK for the tunnel """

    tunnel_sysenvs: list[FirewallRemoteSysEnvConfig]
    """ List of sysenvs behind this tunnel """


@dataclass
class FirewallConfig:
    connections: list[FirewallConnectionConfig]
    """ List of Azure sysenvs to connect to this firewall """

    remote_connections: list[FirewallRemoteConnectionConfig]
    """ List of remote (ipsec) connections to this firewall"""


@dataclass
class FirewallConnectionExport:
    sysenv: str
    supernet: str
    allowed_sysenvs: list[str]


@dataclass
class FirewallExports:
    firewall_id: Output[str]
    connections: list[FirewallConnectionExport]
    supernets: list[str]
