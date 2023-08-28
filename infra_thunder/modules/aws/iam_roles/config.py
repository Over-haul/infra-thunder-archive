from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output

from infra_thunder.lib.iam import RolePolicy


@dataclass
class Role:
    name: str
    """AWS base role name"""

    description: Optional[str]
    """Optional description of this role"""

    policies: Optional[list[RolePolicy]] = field(default_factory=list)
    """Custom IAM policies for this role"""

    buckets: Optional[list[str]] = field(default_factory=list)
    """S3 buckets for this role to access (Optional, shorthand to avoid making custom policy documents)."""

    kinesis: Optional[list[str]] = field(default_factory=list)
    """Kinesis streams for this role to access"""

    sqs: Optional[list[str]] = field(default_factory=list)
    """SQS queues for this role to access"""


@dataclass
class RoleConfig:
    path: Optional[str]
    roles: list[Role]


@dataclass
class RoleExports:
    path: str
    roles: list[Output[str]]
