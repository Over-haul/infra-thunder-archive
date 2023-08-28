from pulumi import ResourceOptions
from pulumi_kubernetes import provider as kubernetes_provider

from infra_thunder.lib.config import tag_namespace
from infra_thunder.lib.kubernetes.constants import SPOT_TAG_KEY
from infra_thunder.lib.kubernetes.helm import HelmChartStack
from infra_thunder.lib.kubernetes.helm.config import HelmChart
from ..config import K8sControllerArgs


def configure_node_feature_discovery(
    provider: kubernetes_provider.Provider,
    cluster_config: K8sControllerArgs,
):
    """
    Configure Node Feature Discovery in the cluster.

    :param provider:
    :param cluster_config:
    :return:
    """
    HelmChartStack(
        "node-feature-discovery",
        namespace=cluster_config.name,
        chart=HelmChart(
            chart="node-feature-discovery",
            repo="https://kubernetes-sigs.github.io/node-feature-discovery/charts",
            version="0.11.1",
            namespace="kube-system",
            values={
                "master": {
                    "resources": {"limits": {"cpu": "100m", "memory": "128Mi"}},
                    # Run anywhere
                    "tolerations": [{"operator": "Exists", "effect": "NoSchedule"}],
                },
                "worker": {
                    "resources": {"limits": {"cpu": "100m", "memory": "128Mi"}},
                    # Tolerate spot instances
                    "tolerations": [
                        {
                            "key": f"{tag_namespace}/{SPOT_TAG_KEY}",
                            "operator": "Exists",
                            "effect": "NoSchedule",
                        }
                    ],
                },
            },
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )
