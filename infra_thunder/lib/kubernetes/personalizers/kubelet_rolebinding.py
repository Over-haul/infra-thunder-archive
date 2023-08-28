from pulumi import ResourceOptions, ComponentResource
from pulumi_kubernetes import meta, rbac


class KubeletRolebinding(ComponentResource):
    """
    Configure a ClusterRoleBinding that allows the APIServer to access logs on Kubelets
    """

    def __init__(self, name: str, opts: ResourceOptions = None):
        super().__init__(
            f"pkg:thunder:kubernetes:personalizers:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )

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
            subjects=[
                rbac.v1.SubjectArgs(
                    api_group="rbac.authorization.k8s.io",
                    kind="User",
                    name="kubernetes",
                )
            ],
            opts=ResourceOptions(parent=self),
        )
