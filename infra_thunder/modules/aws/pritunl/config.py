from dataclasses import dataclass
from typing import Optional

from pulumi import Output


@dataclass
class PritunlArgs:
    client_subnets: list[str]
    """List of CIDRs VPN will use when assigning IPs to clients (Example: 10.5.0.0/16)"""

    peered_subnets: Optional[list[str]]
    """List of CIDRs that require access to this instance's mongodb"""

    mongodb_uri: Optional[str]
    """
    MongoDB connection string URI with passsword
    https://docs.mongodb.com/manual/reference/connection-string/
    Use `pulumi config set --secret pritunl:mongodb_uri mongodb://username:password@host:port/dbname[?options]` # pragma: allowlist secret
    """

    server_id: str
    """VPN server identifier - lower case UUID without dashes (-)"""

    instance_type: Optional[str] = "t3.medium"
    """EC2 Instance Type for Pritunl server"""

    data_volume_size: Optional[int] = 40
    """Size of the EBS volume where pritunl data is stored"""

    data_volume_type: Optional[str] = "gp2"
    """Type of EBS volume where pritunl data is stored (Examples: gp2, io2, st1)"""

    allow_ssh_from_anywhere: Optional[bool] = False
    """
    Allow ssh from anywhere 0.0.0.0/0, only useful when debugging or in case when you cannot access
    instance from within the network
    """


@dataclass
class PritunlExports:
    public_dns: str
    public_ip: Output[str]
    private_ip: Output[str]
    client_subnets: list[str]
    mongodb_uri: str
    server_id: str
