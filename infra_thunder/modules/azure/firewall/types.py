from dataclasses import dataclass

from pulumi_azure_native.network import (
    AwaitableGetVirtualNetworkResult,
    AwaitableGetRouteTableResult,
)

from .config import FirewallConnectionConfig


@dataclass
class FirewallConnection:
    sysenv: str
    network: AwaitableGetVirtualNetworkResult
    route_table: AwaitableGetRouteTableResult
    connection: FirewallConnectionConfig
