from pulumi import ResourceOptions, ComponentResource
from pulumi_azure_native import managedidentity

from infra_thunder.lib.kubernetes.personalizers import *
from .config import K8sControllerConfig
from .personalizers import AADNodeBoostrapper


class AzureClusterPersonalizer(ComponentResource):
    def __init__(
        self,
        name: str,
        cluster_config: K8sControllerConfig,
        cluster_name: str,
        cluster_domain: str,
        endpoint_name: str,
        # bootstrap_role: str,
        # user_roles: list[str],
        coredns_clusterip: str,
        bootstrap_msi: managedidentity.UserAssignedIdentity,
        opts: ResourceOptions = None,
    ):
        super().__init__(f"pkg:thunder:azure:{self.__class__.__name__.lower()}", name, None, opts)

        common_opts = ResourceOptions(parent=self)

        # Configure apiserver -> kubelet ClusterRoleBinding
        KubeletRolebinding("kubelet-rolebinding", opts=common_opts)

        # Configure rolebinding to allow kubelets to renew their serving certificates
        KubeletCSRRenewal("kubelet-csr-renewal", opts=common_opts)

        # Allow nodes to bootstrap
        AADNodeBoostrapper("aad-node-boostrapper", bootstrap_msi=bootstrap_msi, opts=common_opts)

        # Configure rolebinding to allow kubelets to read node secrets
        NodeSecretsRole("node-secrets-role", opts=common_opts)

        # Configure monitoring roles
        MonitoringRoles("monitoring-roles", opts=common_opts)

        # configure a cross-cluster admin account (used by ArgoCD)
        CrossClusterServiceAccount("cross-cluster-serviceaccount", opts=common_opts)

        # AzureAADRoles(
        #     "azure-aad-roles",
        #     bootstrap_role=bootstrap_role,
        #     user_roles=user_roles,
        #     opts=common_opts
        # )

        # Configure Kubernetes Metrics Server
        KubeMetrics("kube-metrics", opts=common_opts)

        # Install Cilium as the CNI
        # TODO: support different CNIs?
        # AzureCiliumCNI(
        #     "azure-cilium-cni",
        #     endpoint=endpoint_name,
        #     opts=common_opts
        # )

        # Install CoreDNS - this must be done AFTER the CNI
        # CoreDNS(
        #     "coredns",
        #     cluster_domain=cluster_domain,
        #     coredns_clusterip=coredns_clusterip,
        #     opts=common_opts
        # )

        # Install Traefik as the Ingress provider
        Traefik("traefik", opts=common_opts)

        # Enable Azure Disk CSI
        # AzureDiskCSI(**common_args)

        # Configure namespaces (default namespaces are gated in the function)
        Namespaces(
            "namespaces",
            extra_namespaces=cluster_config.extra_namespaces,
            opts=common_opts,
        )

        # Configure default deployments
        Charts(
            "charts",
            # extra_charts=cluster_config.extra_charts,
            extra_charts=[],
            opts=common_opts,
        )

        # Install the DD cluster agent
        # DatadogClusterAgent(
        #     "datadog-cluster-agent",
        #     cluster_name=cluster_name,
        #     opts=common_opts
        # )
