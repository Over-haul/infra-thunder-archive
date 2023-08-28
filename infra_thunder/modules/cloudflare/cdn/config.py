from dataclasses import dataclass
from typing import Optional
from .types import RuleSSL, CacheLevel, Polish, RecordType
from pulumi import Output


@dataclass
class Rule:
    target: str
    """The URL pattern to target with the page rule"""

    priority: int
    """Rule Priority"""

    host_header_override: Optional[str]
    """Value of the Host header to send"""

    resolve_override: Optional[str]
    """Overridden origin server name"""

    cache_level: CacheLevel = CacheLevel.basic
    """Whether to set the cache level to 'bypass', 'basic', 'simplified', 'aggressive', or 'cache_everything'"""

    ssl: RuleSSL = RuleSSL.off
    """Whether to set the SSL mode to 'off', 'flexible', 'full', 'strict', or 'origin_pull'"""

    always_use_https: Optional[bool] = False
    """Boolean of whether this action is enabled. Default: false"""

    automatic_https_rewrites: Optional[bool] = True
    """Whether this action is 'on' or 'off'"""

    browser_cache_ttl: Optional[int] = 3600
    """The Time To Live for the browser cache. 0 means 'Respect Existing Headers'"""

    browser_check: Optional[bool] = False
    """Whether this action is 'on' or 'off'"""

    disable_apps: Optional[bool] = False
    """Boolean of whether this action is enabled. Default: false"""

    disable_performance: Optional[bool] = False
    """Boolean of whether this action is enabled. Default: false"""

    disable_security: Optional[bool] = False
    """Boolean of whether this action is enabled. Default: false"""

    disable_zaraz: Optional[bool] = False
    """Boolean of whether this action is enabled. Default: false"""

    ip_geolocation: Optional[bool] = True
    """Whether this action is 'on' or 'off'"""

    mirage: Optional[bool] = True
    """Whether this action is 'on' or 'off'"""

    polish: Polish = Polish.off
    """Whether this action is 'off', 'lossless' or 'lossy'"""

    rocket_loader: Optional[bool] = True
    """Whether this action is 'on' or 'off'"""


@dataclass
class Record:
    name: str
    """The Name of the Record, '*' for wildcard"""

    value: str
    """The Value of the Record"""

    type: RecordType = RecordType.A
    """One of: A AAAA CAA CNAME TXT SRV LOC MX NS SPF CERT DNSKEY DS NAPTR SMIMEA SSHFP TLSA URI PTR"""

    proxied: Optional[bool] = True
    """Shows whether this record can be proxied"""

    ttl: Optional[int] = 60
    """The TTL of the record"""


@dataclass
class Zone:
    name: str
    """Zone Name"""

    records: list[Record]
    """List of Records in Zone"""

    page_rules: Optional[list[Rule]]
    """List of Zone PageRules"""


@dataclass
class CloudflareArgs:
    zones: list[Zone]
    """List of Cloudflare Zones"""


@dataclass
class RuleExports:
    id: Output[str]


@dataclass
class RecordExports:
    id: Output[str]


@dataclass
class ZoneExports:
    name: Output[str]
    id: Output[str]
    rules: list[RecordExports]
    page_rules: list[RuleExports]


@dataclass
class CloudflareExports:
    zones: list[ZoneExports]
