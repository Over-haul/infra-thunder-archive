from pulumi import ComponentResource, ResourceOptions, Output
from pulumi_azure_native import managedidentity
from pulumi_kubernetes import meta, rbac

from infra_thunder.lib.azure.client import get_tenant_id


class AADNodeBoostrapper(ComponentResource):
    """
    Configure AAD Node Bootstrapper RBAC
    """

    def __init__(
        self,
        name: str,
        bootstrap_msi: managedidentity.UserAssignedIdentity,
        opts: ResourceOptions = None,
    ):
        super().__init__(
            f"pkg:thunder:kubernetes:personalizers:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )
        rbac.v1.ClusterRoleBinding(
            "aad-node-boostrapper",
            metadata=meta.v1.ObjectMetaArgs(
                name="thunder:aad-node-boostrapper",
            ),
            subjects=[
                rbac.v1.SubjectArgs(
                    kind="User",
                    name=Output.concat(
                        "https://sts.windows.net/",
                        get_tenant_id(),
                        "/#",
                        bootstrap_msi.principal_id,
                    ),
                    api_group="rbac.authorization.k8s.io",
                )
            ],
            role_ref=rbac.v1.RoleRefArgs(
                api_group="rbac.authorization.k8s.io",
                kind="ClusterRole",
                name="system:node",
            ),
            opts=ResourceOptions(parent=self),
        )
