from pulumi import ComponentResource, ResourceOptions

from infra_thunder.lib.kubernetes.helm import HelmChartComponent, HelmChart


class AADPodIdentity(ComponentResource):
    """
    Configure AAD Pod Identity
    """

    def __init__(self, name: str, opts: ResourceOptions = None):
        super().__init__(
            f"pkg:thunder:kubernetes:personalizers:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )

        HelmChartComponent(
            "aad-pod-identity",
            chart=HelmChart(
                chart="aad-pod-identity",
                repo="https://raw.githubusercontent.com/Azure/aad-pod-identity/master/charts/",
                version="4.1.6",
                namespace="kube-system",
                values={},
            ),
            opts=ResourceOptions(parent=self),
        )
