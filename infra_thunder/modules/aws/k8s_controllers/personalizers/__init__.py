from pulumi import ResourceOptions, Output, ComponentResource, CustomTimeouts
from pulumi_aws import ec2, iam, autoscaling, sqs
from pulumi_kubernetes import provider as kubernetes_provider

from .aws_ebs_csi import configure_aws_ebs_csi
from .aws_iam_authenticator import configure_iam_authenticator
from .aws_node_termination_handler import configure_aws_node_termination_handler
from .cluster_autoscaler import configure_cluster_autoscaler
from .cni import configure_cni
from .coredns import configure_coredns
from .coredns import configure_coredns
from .cross_cluster_access_serviceaccount import (
    configure_cross_cluster_access_serviceaccount,
)
from .datadog_cluster_agent import configure_datadog_cluster_agent
from .datadog_cluster_agent import configure_datadog_cluster_agent
from .deployments import configure_deployments
from .extra_secrets import configure_extra_secrets
from .kube_metrics import configure_kube_metrics
from .kubelet_csr_renewal import configure_csr_renewal
from .kubelet_rolebinding import configure_kubelet_rolebinding
from .monitoring_roles import configure_monitoring_roles
from .namespaces import configure_namespaces
from .node_secrets_role import configure_node_secrets_role
from .node_feature_discovery import configure_node_feature_discovery
from .sealed_secrets import configure_sealed_secrets
from .traefik import configure_traefik
from ..config import K8sControllerArgs
from ..types import IamAuthenticatorRole


def personalize_cluster(
    cls,
    dependency: ComponentResource,
    controllers: list[autoscaling.Group],
    endpoint: Output[str],
    bootstrap_role: iam.Role,
    user_roles: list[tuple[IamAuthenticatorRole, iam.Role]],
    pod_security_groups: list[ec2.SecurityGroup],
    coredns_clusterip: str,
    ebs_controller_role: iam.Role,
    cluster_autoscaler_role: iam.Role,
    node_termination_handler_role: iam.Role,
    node_termination_handler_queue: sqs.Queue,
    kubeconfig: Output[str],
    cluster_config: K8sControllerArgs,
):
    # Create the provider to connect to the cluster
    k8s_provider = kubernetes_provider.Provider(
        "k8s",
        kubeconfig=kubeconfig.future(),
        context=cluster_config.name,
        opts=ResourceOptions(
            parent=dependency,
            depends_on=controllers,
            custom_timeouts=CustomTimeouts(create="15m"),
        ),
    )

    # Configure apiserver -> kubelet ClusterRoleBinding
    configure_kubelet_rolebinding(k8s_provider)

    # Configure rolebinding to allow kubelets to renew their serving certificates
    configure_csr_renewal(k8s_provider)

    # Configure rolebinding to allow kubelets to read node secrets
    configure_node_secrets_role(k8s_provider)

    # Configure monitoring roles
    configure_monitoring_roles(k8s_provider)

    # configure a cross-cluster admin account (used by ArgoCD)
    configure_cross_cluster_access_serviceaccount(k8s_provider)

    # Configure Kubernetes Metrics Server
    configure_kube_metrics(k8s_provider)

    # Configure the IAM authenticator
    if cluster_config.enable_iam_authenticator:
        configure_iam_authenticator(bootstrap_role, user_roles, cluster_config, k8s_provider)

    # Configure the CNI
    configure_cni(cls, endpoint, pod_security_groups, k8s_provider, cluster_config)

    # Configure DNS
    if cluster_config.enable_coredns:
        configure_coredns(coredns_clusterip, k8s_provider, cluster_config)

    configure_traefik(k8s_provider, cluster_config)

    configure_aws_ebs_csi(k8s_provider, ebs_controller_role, cluster_config)

    # Configure namespaces (default namespaces are gated in the function)
    configure_namespaces(cluster_config, k8s_provider)

    # Configure extra secrets
    configure_extra_secrets(cluster_config, k8s_provider)

    # Configure default deployments
    configure_deployments(k8s_provider, cluster_config)

    configure_datadog_cluster_agent(k8s_provider, cluster_config)

    # Configure sealed-secrets
    if cluster_config.enable_sealed_secrets:
        configure_sealed_secrets(k8s_provider, cluster_config)

    configure_node_feature_discovery(k8s_provider, cluster_config)

    # Configure AWS Node Termination Handler
    configure_aws_node_termination_handler(
        k8s_provider, node_termination_handler_role, node_termination_handler_queue, cluster_config
    )

    configure_cluster_autoscaler(k8s_provider, cluster_autoscaler_role, cluster_config, cls.region)
