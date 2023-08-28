from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output


@dataclass
class DNSRecord:
    name: str
    """DNS Record Name"""

    records: Optional[list[str]]
    """A string list of record values. To specify a single record value longer than 255 characters such as a TXT record
    for DKIM, add \"\" inside the configuration string (e.g. "first255characters\"\"morecharacters")."""

    type: str
    """One of: A, AAAA, CNAME, TXT"""

    ttl: Optional[int] = 60
    """Record TTL. Defaults to 60 if not present."""


@dataclass
class HostedZoneArgs:
    name: Optional[str]
    """HostedZone name."""

    base_domain: Optional[str]
    """Allows you to override the default base domain if desired."""

    comment: Optional[str]
    """Comment or description for this HostedZone."""

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
