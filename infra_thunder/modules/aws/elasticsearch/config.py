from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output


@dataclass
class ClusterConfig:
    name: Optional[str]
    """Domain Name."""

    instance_type: str
    """Instance type of data nodes in the cluster."""

    dedicated_master_type: Optional[str]
    """
    Instance type of the dedicated main nodes in the cluster.
    Passing a value implicitly indicates the need for dedicated masters.
    Sets master count to 3.
    """

    elasticsearch_version: Optional[str] = "OpenSearch_1.0"
    """Version of Elasticsearch to deploy."""

    instance_count_per_zone: Optional[int] = 1
    """
    Number of instances per each of the 3 availability zones in the cluster.
    A value of 1 implies 3 instances, one in each az.
    """

    ebs_volume_size: Optional[int] = 10
    """Size of EBS volumes attached to data nodes (in GiB)."""

    advanced_options: Optional[dict[str, str]] = field(default_factory=dict[str, str])
    """
    Advanced options. The options and their descriptions may be found at
    https://docs.aws.amazon.com/opensearch-service/latest/developerguide/ac.html#ac-advanced
    """

    disable_authentication: Optional[bool] = True
    """Disable all elasticsearch security and allow on-network clients access."""


@dataclass
class ElasticSearchConfig:
    clusters: list[ClusterConfig]


@dataclass
class ClusterExports:
    name: str

    arn: Output[str]

    domain_id: Output[str]

    endpoint: Output[str]

    id: Output[str]


@dataclass
class ElasticSearchExports:
    clusters: list[ClusterExports]
