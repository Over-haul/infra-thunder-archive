from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output
from pulumi_aws.acm import outputs as acm_outputs

from infra_thunder.lib.iam import RolePolicy


@dataclass
class TargetGroup:
    name: str
    """Name of the target group"""

    ssl_domains: list[str]
    """List of the SSL domains this target group is valid for"""

    acm_cert_arn: str = None
    """ARN of the ACM SSL certificate to use for this target group"""


# Can be used in near future
# @dataclass
# class SpotInstancesConfig:
# on_demand_allocation_strategy: str = "prioritized"
# """Strategy to use when launching on-demand instances. Valid values: prioritized. Default: prioritized."""
# on_demand_base_capacity: int = 0
# """Absolute minimum amount of desired capacity that must be fulfilled by on-demand instances"""
# on_demand_percentage_above_base_capacity: int = 0
# """Percentage split between on-demand and Spot instances above the base on-demand capacity"""
# spot_allocation_strategy: str = "capacity-optimized"
# """How to allocate capacity across the Spot pools. Valid values: lowest-price, capacity-optimized, capacity-optimized-prioritized"""
# spot_instance_pools: int = 0
# """Number of Spot pools per availability zone to allocate capacity. EC2 Auto Scaling selects the cheapest Spot pools and evenly allocates Spot capacity across the number of Spot pools that you specify"""
# spot_max_price: Optional[str] = None
# """Maximum price per unit hour that the user is willing to pay for the Spot instances. An empty string which means the on-demand price"""
# instance_types: list[str] = field(default_factory=list)
# """List of instances to be used in spot requests"""


@dataclass
class NodeGroup:
    name: str
    """Name of the NodeGroup"""

    max_size: int
    """Maximum amount of nodes to launch in this NodeGroup"""

    min_size: int = 1
    """Minimum amount of nodes to launch in this NodeGroup"""

    instance_type: str = "t3.xlarge"
    """Type of the instances launched in this NodeGroup"""

    rootfs_size_gb: int = 20
    """Size of the agent rootfs in GB"""

    dockervol_size_gb: int = 20
    """Size of the docker volume in GB"""

    labels: list[str] = field(default_factory=list)
    """Labels to apply to nodes in this NodeGroup"""

    dockervol_type: str = "gp2"
    """Type of EBS volume for the dockervol (gp2, st1,...)"""

    include_default_targetgroup: bool = True
    """Should this NodeGroup be included in the default targetgroup"""

    extra_targetgroups: list[str] = field(default_factory=list)
    """Extra target groups to associate with this NodeGroup"""

    spot_instances: bool = False
    """Should this NodeGroup run SpotInstances"""

    dedicated: bool = False
    """Should this NodeGroup be maked as Dedicated (via k8s taints)"""

    # Can be used in near future
    # spot_instances: SpotInstancesConfig = field(default_factory=SpotInstancesConfig)
    # """Should this NodeGroup use SpotInstances"""

    # TODO: add autoscaling enabled flag (append autoscaling tag)
    # TODO: add taints, support adding labels


@dataclass
class K8sAgentArgs:
    cluster: Optional[str]
    """The K8s cluster to associate these NodeGroups with"""

    nodegroups: list[NodeGroup]
    """NodeGroups to add to this K8s cluster"""

    custom_iam_policies: Optional[list[RolePolicy]] = field(default_factory=list)
    """Custom IAM policies for this NodeGroup"""

    extra_ssl_domains: list[str] = field(default_factory=list)
    """Extra SSL domains to add to the default target group"""

    extra_targetgroups: list[TargetGroup] = field(default_factory=list)
    """Extra target groups for ingress"""

    enable_glb: bool = True
    """Enable the Gateway Load Balancer endpoint for ClusterIP connections"""

    docker_registry_cache: Optional[str] = field(default_factory=str)
    """Docker Registry Mirror/Cache URL: https://reg.example.com"""


@dataclass
class K8sAgentConfig:
    agents: list[K8sAgentArgs]


@dataclass
class K8sTargetGroupExports:
    name: str
    """Name of the target group"""

    id: Output[str]
    """ID of the target group"""

    dns_name: Output[str]
    """Route53 record for the ALB associated with this target group"""

    acm_certificate_arn: Output[str]
    """ACM certificate ARN for this target group"""

    acm_ssl_validation_records: Optional[list[Output[acm_outputs.CertificateDomainValidationOption]]] = None
    """Map of DNS records to support the SSL certificate"""


@dataclass
class K8sAgentExports:
    cluster: str
    """Cluster these nodes belong to"""

    role_arn: Output[str]
    """IAM Role ARN for all NodeGroups"""

    default_targetgroup: K8sTargetGroupExports
    """Default target group"""

    extra_targetgroups: list[K8sTargetGroupExports]
    """Extra target groups created by these NodeGroups"""

    nodegroups: list[str]
    """List of NodeGroups"""
