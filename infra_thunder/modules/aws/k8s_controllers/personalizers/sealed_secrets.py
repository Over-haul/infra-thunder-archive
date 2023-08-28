from pulumi import ResourceOptions
from pulumi_kubernetes import provider as kubernetes_provider

from infra_thunder.lib.kubernetes.helm import HelmChartStack
from infra_thunder.lib.kubernetes.helm.config import HelmChart
from ..config import K8sControllerArgs


def configure_sealed_secrets(provider: kubernetes_provider.Provider, cluster_config: K8sControllerArgs):
    """
    Configure the bitnami SealedSecrets chart

    :return:
    """
    HelmChartStack(
        "sealed-secrets-controller",
        namespace=cluster_config.name,
        chart=HelmChart(
            chart="sealed-secrets",
            repo="https://bitnami-labs.github.io/sealed-secrets",
            namespace="kube-system",
            version="2.1.7",
            values={
                "tolerations": [{"operator": "Exists", "effect": "NoSchedule"}],
            },
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )
