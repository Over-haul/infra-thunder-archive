from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output


@dataclass
class MySQLParameter:
    name: str
    """The name of the RDS parameter."""

    value: str
    """The value of the RDS parameter."""

    apply_method: Optional[str] = "immediate"
    """One of `immediate` for dynamic params or `pending-reboot` for static."""


@dataclass
class Replica:
    availability_zone: str
    """A-Z into which this replica should be placed."""


@dataclass
class MySQLInstance:
    name: str
    """Name of the DB instance."""

    snapshot_identifier: Optional[str]
    """Specifies whether or not to create this database from a snapshot."""

    engine_version: str = "8.0.27"
    """Engine version of the DB to use."""

    allocated_storage: int = 20
    """Initial allocated storage size in GiB."""

    multi_az: bool = True
    """Enable/Disable Multi-AZ Support."""

    instance_type: str = "db.t3.medium"
    """AWS Instance Type to use: https://aws.amazon.com/rds/instance-types/"""

    db_parameters: Optional[list[MySQLParameter]] = field(default_factory=list)
    """Extra configuration params for RDS."""

    replicas: Optional[list[Replica]] = field(default_factory=list)
    """Optional configuration for cross A-Z replicas."""


@dataclass
class MySQLInstances:
    instances: list[MySQLInstance]
    """List of RDS Instances to create."""


@dataclass
class MySQLInstanceExport:
    address: Output[str]
    """The hostname of the RDS instance."""

    arn: Output[str]
    """Amazon Resource Name (ARN) for the RDS instance."""

    endpoint: Output[str]
    """The connection endpoint in `address:port` format."""

    hosted_zone_id: Output[str]
    """The canonical hosted zone id of the DB instance to be used in a Route53 Alias record."""

    id: Output[str]
    """AWS-assigned ID."""

    resource_id: Output[str]
    """The RDS resource ID of this instance."""

    password: Output[str]
    """Database admin password"""

    snapshot_identifier: Optional[str] = None
    """Snapshot ID used to create this instance"""


@dataclass
class MySQLExports:
    name: str
    """Exported name of this Instance."""

    instance: MySQLInstanceExport

    replicas: list[MySQLInstanceExport]
