from pulumi import ResourceOptions
from pulumi_kubernetes import provider as kubernetes_provider
from pulumi_kubernetes import rbac, core, meta


def configure_cross_cluster_access_serviceaccount(
    provider: kubernetes_provider.Provider,
):
    """
    Configures a ServiceAccount to allow cross-cluster access to manage this K8s cluster.

    :param provider:
    :return:
    """

    # Create a serviceAccount for this
    cross_cluster_sa = core.v1.ServiceAccount(
        "cross-cluster-admin-sa",
        metadata=meta.v1.ObjectMetaArgs(name="thunder-cross-cluster-admin", namespace="kube-system"),
        opts=ResourceOptions(parent=provider, provider=provider),
    )

    # Bind the role to the service account group
    rbac.v1.ClusterRoleBinding(
        "cross-cluster-rolebinding",
        metadata=meta.v1.ObjectMetaArgs(name="thunder-cross-cluster-admin", namespace="kube-system"),
        subjects=[
            rbac.v1.SubjectArgs(
                kind="ServiceAccount",
                name=cross_cluster_sa.metadata.name,
                namespace=cross_cluster_sa.metadata.namespace,
            )
        ],
        role_ref=rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name="cluster-admin",
        ),
        opts=ResourceOptions(parent=cross_cluster_sa, provider=provider),
    )
