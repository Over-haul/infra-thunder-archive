from dataclasses import dataclass, field
from typing import Optional, Sequence

from pulumi import Output


@dataclass
class ReplicationGroupParam:
    name: str
    """The name of the Elasticache parameter."""

    value: str
    """The value of the Elasticache parameter."""


@dataclass
class ReplicationGroup:
    name: str
    """Replication Group name."""

    engine: str
    """Engine name, currently 'redis'"""

    engine_version: str
    """
    Supported engine version, currently '6.x'.
    See: https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/supported-engine-versions.html#redis-version-6.x
    """

    instance_type: str
    """Supported instance type. See: https://aws.amazon.com/elasticache/pricing/"""

    automatic_failover: bool
    """Enable automatic failover or not. Required true if num_node_groups > 1."""

    num_node_groups: int
    """Number of node groups or 'shards'"""

    replicas_per_node_group: int
    """Number of replicas (doesn't count master) nodes per node group."""

    availability_zones: Optional[list[str]] = field(default_factory=list)
    """Desired AZs for the node groups."""

    rg_params: Optional[list[ReplicationGroupParam]] = field(default_factory=list)
    """List of cluster configuration options."""

    transit_encryption_enabled: bool = False
    """Whether to enable encryption in transit."""


@dataclass
class ReplicationGroups:
    replication_groups: list[ReplicationGroup]
    """List of Replication Group specifications."""


@dataclass
class ElasticacheExports:
    auth_token: Output[str]
    """
    The password used to access a password protected server.
    Can be specified only if ``transit_encryption_enabled = true``
    """

    id: Output[str]
    """The provider-assigned unique ID for this managed resource."""

    member_clusters: Output[Sequence[str]]
    """The identifiers of all the nodes that are part of this replication group."""

    primary_endpoint_address: Output[str]
    """The address of the endpoint for the primary node in the replication group, if the cluster mode is disabled."""
