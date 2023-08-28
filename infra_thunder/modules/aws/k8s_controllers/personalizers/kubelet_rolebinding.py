from pulumi import ResourceOptions

from pulumi_kubernetes import meta, rbac
from pulumi_kubernetes import provider as kubernetes_provider


def configure_kubelet_rolebinding(provider: kubernetes_provider.Provider):
    """
    Configure a ClusterRoleBinding that allows the APIServer to access logs on Kubelets
    :param cluster_config: Kubernetes Cluster Configuration
    :param provider: Kubernetes provider
    :return:
    """
    rbac.v1.ClusterRoleBinding(
        "kube-apiserver-to-kubelet",
        metadata=meta.v1.ObjectMetaArgs(
            name="system:kube-apiserver-to-kubelet",
        ),
        role_ref=rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name="system:kubelet-api-admin",
        ),
        subjects=[rbac.v1.SubjectArgs(api_group="rbac.authorization.k8s.io", kind="User", name="kubernetes")],
        opts=ResourceOptions(parent=provider, provider=provider),
    )
