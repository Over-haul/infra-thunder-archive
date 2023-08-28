from pulumi import ResourceOptions
from pulumi_kubernetes import provider as kubernetes_provider

from infra_thunder.lib.kubernetes.helm import HelmChartStack
from ..config import K8sControllerArgs
from ..defaults import default_services


def configure_deployments(provider: kubernetes_provider.Provider, cluster_config: K8sControllerArgs):
    if cluster_config.install_default_services:
        # install default services
        for chart in default_services:
            HelmChartStack(
                chart.chart,
                namespace=cluster_config.name,
                chart=chart,
                opts=ResourceOptions(parent=provider, provider=provider),
            )

    for chart in cluster_config.extra_helm_charts:
        # install extra helm charts
        HelmChartStack(
            chart.chart,
            namespace=cluster_config.name,
            chart=chart,
            opts=ResourceOptions(parent=provider, provider=provider),
        )
