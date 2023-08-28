from pulumi import ResourceOptions, ComponentResource

from pulumi_kubernetes import meta, rbac


class KubeletCSRRenewal(ComponentResource):
    """
    Configure a ClusterRoleBinding that allows the Kubelets to renew their kubelet-serving CSRs
    """

    def __init__(self, name: str, opts: ResourceOptions = None):
        super().__init__(
            f"pkg:thunder:kubernetes:personalizers:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )

        rbac.v1.ClusterRoleBinding(
            "kubelet-csr-renewal",
            metadata=meta.v1.ObjectMetaArgs(
                name="system:kubelet-csr-renewal",
                # namespace="kube-system"
            ),
            subjects=[
                rbac.v1.SubjectArgs(
                    kind="Group",
                    name="system:nodes",
                    api_group="rbac.authorization.k8s.io",
                )
            ],
            role_ref=rbac.v1.RoleRefArgs(
                api_group="rbac.authorization.k8s.io",
                kind="ClusterRole",
                name="system:certificates.k8s.io:certificatesigningrequests:selfnodeclient",
            ),
            opts=ResourceOptions(parent=self),
        )
