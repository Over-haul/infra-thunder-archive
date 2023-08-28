from pulumi import ResourceOptions, ComponentResource
from pulumi_kubernetes import rbac, core, meta


class CrossClusterServiceAccount(ComponentResource):
    """
    Configures a ServiceAccount to allow cross-cluster access to manage this K8s cluster.
    """

    def __init__(self, name: str, opts: ResourceOptions = None):
        super().__init__(
            f"pkg:thunder:kubernetes:personalizers:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )

        # Create a serviceAccount for this
        cross_cluster_sa = core.v1.ServiceAccount(
            "cross-cluster-admin-sa",
            metadata=meta.v1.ObjectMetaArgs(name="thunder-cross-cluster-admin", namespace="kube-system"),
            opts=ResourceOptions(parent=self),
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
            opts=ResourceOptions(parent=self),
        )
