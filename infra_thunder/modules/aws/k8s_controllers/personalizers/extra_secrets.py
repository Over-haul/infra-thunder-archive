from pulumi import ResourceOptions
from pulumi_kubernetes import core, meta
from pulumi_kubernetes import provider as kubernetes_provider

from ..config import K8sControllerArgs, K8sSecret


def configure_extra_secrets(cluster_config: K8sControllerArgs, provider: kubernetes_provider.Provider):
    """
    Add any extra secrets from the cluster configuration
    :param cluster_config: Kubernetes Cluster Configuration
    :param provider: Kubernetes provider
    :return:
    """

    for secret in cluster_config.extra_secrets:
        _add_secret(secret, provider)


def _add_secret(secret: K8sSecret, provider: kubernetes_provider.Provider):
    core.v1.Secret(
        f"secret/{secret.namespace}/{secret.name}",
        type="Opaque",
        metadata=meta.v1.ObjectMetaArgs(
            name=secret.name, namespace=secret.namespace, labels=secret.labels, annotations=secret.annotations
        ),
        string_data=secret.string_data,
        opts=ResourceOptions(parent=provider, provider=provider),
    )
