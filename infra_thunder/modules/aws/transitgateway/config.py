from dataclasses import dataclass

from pulumi import Output


@dataclass
class TransitGatewayConnectionConfig:
    profile: str
    """Which AWS profile (~/.aws/config) should be used to connect to this remote SysEnv?"""

    sysenv: str
    """What is the SysEnv name to operate against?"""

    allowed_sysenvs: list[str]
    """Which SysEnvs should be allowed to connect to this SysEnv?"""


@dataclass
class TransitGatewayConfig:
    connections: list[TransitGatewayConnectionConfig]


@dataclass
class TransitGatewayConnectionExport:
    sysenv: str
    supernet: str
    allowed_sysenvs: list[str]


@dataclass
class TransitGatewayExports:
    tgw_id: Output[str]
    connections: list[TransitGatewayConnectionExport]
    supernets: list[str]


"""
{
    tgw_id: 123,
    supernets: [ 10.10.0.0/16, 10.20.0.0/16, 10.30.0.0/16 ]
    connections: [
        {
            sysenv: tools
            supernet: 10.10.0.0/16
            allowed_sysenvs: [ prod, dev, sandbox ]
        },
        {
            sysenv: prod,
            supetnet: 10.20.0.0/16
            allowed_sysenvs: [ tools ]
        }
        {
            sysenv: dev,
            supernet: 10.30.0.0/16
            allowed_sysenvs: [ tools ]
        }
        {
            sysenv: sandbox,
            supetnet: 10.40.0.0/16
            allowed_sysenvs: [ tools ]
        }
    ]
}

"""
