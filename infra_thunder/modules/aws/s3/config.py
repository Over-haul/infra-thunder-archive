from dataclasses import dataclass

from pulumi import Output


@dataclass
class S3BucketArgs:
    name: str
    """Bucket name"""

    acl: str = "private"
    """Bucket ACLs"""

    versioning: bool = True
    """Whether this bucket should be versioned or not"""


@dataclass
class S3Args:
    buckets: list[S3BucketArgs]
    """List of S3 Bucket configurations"""


@dataclass
class S3Exports:
    bucket: Output[str]
    """Bucket name"""

    friendly_name: str
    """Bucket name without the sysenv prefix"""

    bucket_domain_name: Output[str]
    """Bucket domain name"""

    region: Output[str]
    """AWS region in which this bucket resides"""
