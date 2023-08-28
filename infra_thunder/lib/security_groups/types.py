from dataclasses import dataclass
from typing import Optional


@dataclass
class SecurityGroupIngressRule:
    description: str
    """Description of the rule"""

    from_port: int
    """The start port (or ICMP type number if protocol is "icmp" or "icmpv6")"""

    to_port: int
    """The end port (or ICMP code if protocol is "icmp")"""

    protocol: str
    """
    The protocol. If not icmp, icmpv6, tcp, udp, or all use the
    [protocol number](https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml)
    """

    allow_vpc_supernet: Optional[bool] = None
    """Allow all members of this VPC supernet access to this rule"""

    allow_peered_supernets: Optional[bool] = None
    """Allow peered supernets to access this rule"""

    cidr_blocks: Optional[list[str]] = None
    """List of CIDR blocks. Cannot be specified with `source_security_group_id`"""

    source_security_group_id: Optional[str] = None
    """
    The security group id to allow access to/from,
    depending on the `type`. Cannot be specified with `cidr_blocks` and `self`
    """

    self: Optional[bool] = False
    """
    If true, the security group itself will be added as
    a source to this ingress rule. Cannot be specified with `source_security_group_id`
    """
