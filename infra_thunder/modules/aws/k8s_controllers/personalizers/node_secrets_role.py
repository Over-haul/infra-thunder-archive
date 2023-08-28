from pulumi import ResourceOptions
from pulumi_kubernetes import provider as kubernetes_provider
from pulumi_kubernetes import rbac, meta

from infra_thunder.lib.kubernetes.constants import MONITORING_SECRET_NAME


def configure_node_secrets_role(provider: kubernetes_provider.Provider):
    """
    Configure a role that allows nodes (in the `system:bootstrappers` group) to access a secret that contains any
    information needed to bootstrap a new node in the cluster.

    Example:
        Before starting the kubelet process on node `mynode-1`, a boot script
        uses the kubelet's kubeconfig file to download the `node-secrets` secret to the node.
        Some time later, another process may then consume that secrets file (for example a monitoring API key).

    :param provider:
    :return:
    """

    # Create a role that allows access to the `node-secrets` secret in the `kube-system` namespace
    node_secret_role = rbac.v1.Role(
        "node-secrets-role",
        metadata=meta.v1.ObjectMetaArgs(name="system:node-secrets", namespace="kube-system"),
        rules=[
            rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=["secrets"],
                resource_names=["node-secrets", MONITORING_SECRET_NAME],
                verbs=["get"],
            )
        ],
        opts=ResourceOptions(parent=provider, provider=provider),
    )

    # Bind the role to the system:bootstrappers group
    rbac.v1.RoleBinding(
        "node-secrets-rolebinding",
        # api_version="rbac.authorization.k8s.io/v1",
        metadata=meta.v1.ObjectMetaArgs(name="system:node-secrets", namespace="kube-system"),
        subjects=[
            rbac.v1.SubjectArgs(
                kind="Group",
                api_group="rbac.authorization.k8s.io",
                name="system:bootstrappers",
            )
        ],
        role_ref=rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="Role",
            name=node_secret_role.metadata.name,
        ),
        opts=ResourceOptions(parent=node_secret_role, provider=provider),
    )
