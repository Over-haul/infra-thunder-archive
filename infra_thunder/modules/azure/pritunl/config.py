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

    instance_type: Optional[str] = "Standard_B2s"
    """EC2 Instance Type for Pritunl server"""

    data_volume_size: Optional[int] = 40
    """Size of the EBS volume where pritunl data is stored"""


@dataclass
class PritunlExports:
    public_dns: str
    public_ip: Output[str]
    private_ip: Output[str]
    client_subnets: list[str]
    mongodb_uri: str
    server_id: str
