from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output


@dataclass
class DNSRecord:
    name: str
    """DNS Record Name"""

    type: str
    """One of: A, AAAA, CNAME, TXT"""

    ttl: Optional[int] = 60
    """Record TTL. Defaults to 60 if not present."""

    records: Optional[list[str]] = field(default_factory=list)
    """Actual DNS record(s)"""


@dataclass
class HostedZoneArgs:
    name: Optional[str]
    """HostedZone name."""

    base_domain: Optional[str]
    """Allows you to override the default base domain if desired."""

    records: Optional[list[DNSRecord]] = field(default_factory=list)
    """List of DNSRecords to add to this HostedZone."""


@dataclass
class HostedZoneArgsList:
    sysenv_zone: HostedZoneArgs
    """Base sysenv hosted zone config."""

    extra_zones: Optional[list[HostedZoneArgs]]
    """List of other, optional hosted zones."""


@dataclass
class HostedZoneExports:
    fqdn: Output[str]
    """Fully qualified domain name of this HostedZone."""

    name_servers: Output[list[str]]
    """List of name servers for this zone."""

    zone_id: Output[str]
    """Zone ID, referenceable by zone records."""
