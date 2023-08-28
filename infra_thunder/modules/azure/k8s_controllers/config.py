from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output

from infra_thunder.lib.kubernetes.helm import HelmChart


@dataclass
class K8sControllerConfig:
    service_cidr: str
    """CIDR for services"""

    extra_namespaces: Optional[list[str]] = field(default_factory=list)
    """Extra default namespaces"""

    extra_helm_charts: Optional[list[HelmChart]] = field(default_factory=list)
    """Extra helm charts to add to this cluster by default"""

    instance_type: str = "Standard_D4_v3"
    """Instance type of the controllers"""

    rootfs_size_gb: int = 20
    """Rootfs size of the controllers"""

    cni_provider: str = "azure-cni"
    """Cluster CNI provider"""

    enable_coredns: bool = True
    """Enable CoreDNS addon"""

    coredns_clusterip_index: int = 10
    """CoreDNS ClusterIP index. (Pick the nth IP from the service_cidr to use as the cluster_ip)"""

    install_default_namespaces: bool = True
    """Create default namespaces in this cluster (see `defaults.py` for list of namespaces)?"""

    install_default_services: bool = True
    """Install default services via helm (see `defaults.py` for list of services)?"""

    dd_forward_audit_logs: bool = False
    """Forward Kubernetes API Server Audit Logs to Datadog"""

    e2d_snapshot_retention_time: int = 3
    """Days to keep e2d snapshots for"""


@dataclass
class K8sControllerAgentSecretsExports:
    vault_id: Output[str]
    """The Azure KeyVault ID that contains the CA certificate"""

    vault_secrets: dict[str, Output[str]]
    """Dict of {NAME: ID} of secrets in vault"""


@dataclass
class K8sControllerExports:
    name: str
    """Cluster name"""

    endpoint: str
    """kube-api endpoint"""

    internal_endpoint: str
    """kube-api internal (dns) endpoint"""

    service_cidr: str
    """The Kubernetes service IPv4 CIDR"""

    coredns_clusterip: str
    """CoreDNS ClusterIP inside the service CIDR"""

    cluster_domain: str
    """CoreDNS cluster domain"""

    pod_nsg: Output[str]
    """Network Security Group for pods"""

    admin_kubeconfig: Output[str]
    """Administrator PKI-based Kubeconfig for this cluster"""

    # iam_kubeconfig: Output[str]
    # """IAM (user) Kubeconfig for this cluster"""

    agent_bootstrap_msi_id: Output[str]
    """Resource ID of the bootstrapper MSI that agents need to utilize to join the cluster"""

    agent_secrets: K8sControllerAgentSecretsExports
