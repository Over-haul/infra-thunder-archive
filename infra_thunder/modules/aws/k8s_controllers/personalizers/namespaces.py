from pulumi import ResourceOptions
from pulumi_kubernetes import core, meta
from pulumi_kubernetes import provider as kubernetes_provider

from ..config import K8sControllerArgs
from ..defaults import default_namespaces


def configure_namespaces(cluster_config: K8sControllerArgs, provider: kubernetes_provider.Provider):
    """
    Configure the default namespaces and add any extras from the cluster configuration
    :param cluster_config: Kubernetes Cluster Configuration
    :param provider: Kubernetes provider
    :return:
    """
    if cluster_config.install_default_namespaces:
        for ns in default_namespaces:
            _add_namespace(ns, provider)

    for ns in cluster_config.extra_namespaces:
        _add_namespace(ns, provider)


def _add_namespace(ns: str, provider: kubernetes_provider.Provider):
    core.v1.Namespace(
        f"ns/{ns}",
        metadata=meta.v1.ObjectMetaArgs(
            name=ns,
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )
