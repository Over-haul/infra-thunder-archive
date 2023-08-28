from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output

from infra_thunder.lib.kubernetes.helm import HelmChart


@dataclass
class K8sSecret:
    name: str
    """Name of the secret"""

    namespace: str
    """Namespace where to store the secret"""

    string_data: dict[str, str]
    """Allows specifying non-binary secret data in string form"""

    labels: Optional[dict[str, str]]
    """Map of string keys and values that can be used to organize and categorize (scope and select) objects"""

    annotations: Optional[dict[str, str]]
    """
    Annotations is an unstructured key value map stored with a resource that
    may be set by external tools to store and retrieve arbitrary metadata
    """


@dataclass
class CoreDNSDomains:
    sysenv: str
    """SysEnv name"""

    resolver: str
    """Resolver address"""


@dataclass
class K8sControllerArgs:
    name: Optional[str]
    """Name of the Kubernetes cluster"""

    service_cidr: str
    """CIDR for services"""

    cluster_domain: Optional[str]
    """Cluster DNS domain"""

    node_termination_webhook_url: Optional[str]
    """Webhook URL for AWS autoscaling group interruption events"""

    node_termination_webhook_template: Optional[str]
    """
    Template for the webhook payload
    Available nodeMetadata fields: https://github.com/aws/aws-node-termination-handler/blob/e617cc3f79a29912d76231d15d139de98455ea23/pkg/ec2metadata/ec2metadata.go#L108-L119
    Available InterruptionEvent fields: https://github.com/aws/aws-node-termination-handler/blob/701db81ccfb58d94c2b6df2b1bd273a442a4d05e/pkg/monitor/types.go#L27-L45
    .NodeLabels are available thanks to https://github.com/imuqtadir/aws-node-termination-handler/blob/ccaae0544f0971ca80f501734fdb5b70952a3235/pkg/node/node.go#L285-L296
    .Pods are available thanks to https://github.com/aws/aws-node-termination-handler/blob/37e989956e163b027cd2dcc04a58ce89a75244c6/cmd/node-termination-handler.go#L344
    """

    extra_namespaces: Optional[list[str]] = field(default_factory=list)
    """Extra default namespaces"""

    extra_helm_charts: Optional[list[HelmChart]] = field(default_factory=list)
    """Extra helm charts to add to this cluster by default"""

    extra_secrets: Optional[list[K8sSecret]] = field(default_factory=list)
    """Extra Opaque secrets to add to this cluster"""

    coredns_domains: Optional[list[CoreDNSDomains]] = field(default_factory=list)
    """Peered CoreDNS domains"""

    instance_type: str = "t3.xlarge"
    """Instance type of the controllers"""

    rootfs_size_gb: int = 20
    """Rootfs size of the controllers"""

    cni_provider: str = "aws-cni"
    """Cluster CNI provider"""

    enable_iam_authenticator: bool = True
    """Enable the AWS IAM authenticator"""

    enable_coredns: bool = True
    """Enable CoreDNS addon"""

    enable_sealed_secrets: bool = False
    """Enable Sealed Secrets addon"""

    coredns_clusterip_index: int = 10
    """CoreDNS ClusterIP index. (Pick the nth IP from the service_cidr to use as the cluster_ip)"""

    install_default_namespaces: bool = True
    """Create default namespaces in this cluster (see `defaults.py` for list of namespaces)?"""

    install_default_services: bool = True
    """Install default services via helm (see `defaults.py` for list of services)?"""

    enable_clusterip_routes: bool = False
    """Route external ClusterIP access via the controllers"""

    dd_forward_audit_logs: bool = False
    """Forward Kubernetes API Server Audit Logs to Datadog"""

    docker_registry_cache: Optional[str] = field(default_factory=str)
    """Docker Registry Mirror/Cache URL: https://reg.example.com"""


@dataclass
class K8sControllerConfig:
    clusters: list[K8sControllerArgs]

    backups_bucket: Optional[str]

    e2d_snapshot_retention_time: int = 3
    """Days to keep e2d snapshots for"""


@dataclass
class K8sControllerExports:
    name: str
    """Cluster name"""

    endpoint: Output[str]
    """kube-api endpoint"""

    service_cidr: str
    """The Kubernetes service IPv4 CIDR"""

    coredns_clusterip: str
    """CoreDNS ClusterIP inside the service CIDR"""

    cluster_domain: str
    """CoreDNS cluster domain"""

    bootstrap_role_arn: Output[str]
    """Role to be assumed by nodes wishing to join the cluster"""

    admin_kubeconfig: Output[str]
    """Administrator PKI-based Kubeconfig for this cluster"""

    is_admin_cert_expired: Output[bool]
    """True or False depending on admin cert expiration date"""

    iam_kubeconfig: Output[str]
    """IAM (user) Kubeconfig for this cluster"""
