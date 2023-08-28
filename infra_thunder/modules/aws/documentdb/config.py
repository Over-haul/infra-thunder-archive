from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output


@dataclass
class ClusterParameter:
    name: str
    """The name of the DocumentDB parameter"""

    value: str
    """The value of the DocumentDB parameter"""


@dataclass
class Cluster:
    name: str
    """Name for the DocumentDB cluster (Example: logs)"""

    engine_version: str = "4.0.0"
    """The database engine version"""

    instance_type: str = "db.t3.medium"
    """EC2 Instance Type for DocumentDB members"""

    count: int = 3
    """Cluster member count"""

    cluster_parameters: Optional[list[ClusterParameter]] = field(default_factory=list)
    """A list of DocumentDB parameters to apply"""


@dataclass
class DocumentDBArgs:
    clusters: list[Cluster]
    """List of DocumentDB clusters to create"""


@dataclass
class DocumentDBExports:
    arn: Output[str]
    """Amazon Resource Name (ARN) for the DocumentDB cluster"""

    cluster_resource_id: Output[str]
    """Resource ID for the DocumentDB Cluster"""

    endpoint: Output[str]
    """The DNS address of the DocumentDB instance"""

    hosted_zone_id: Output[str]
    """The Route53 Hosted Zone ID of the endpoint"""

    id: Output[str]
    """The provider-assigned unique ID for this managed resource"""

    reader_endpoint: Output[str]
    """A read-only endpoint for the DocDB cluster, automatically load-balanced across replicas"""

    instances_arn: list[Output[str]]
    """Amazon Resource Name (ARN) of cluster instances"""

    master_username: Output[str]
    """Username for the master DB user"""

    master_password: Output[str]
    """Password for the master DB user. Note that this may show up in logs, and it will be stored in the state file"""
