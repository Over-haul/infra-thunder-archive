from pulumi import ResourceOptions, ComponentResource

from infra_thunder.lib.kubernetes.helm import HelmChartComponent, HelmChart

DEFAULT_CHARTS = [
    # for auto approving kubelet serving csrs
    HelmChart(
        chart="kubelet-rubber-stamp",
        repo="https://flexkube.github.io/charts/",
        namespace="kube-system",
        version="0.1.6",
        values={
            # TODO: need to add node-role to control planes to allow it to run this container...
        },
    ),
    # for allowing IAM namespaced (AssumeRole) pods
    # TODO: allow deploying this depending on cluster provider
    # HelmChart(
    #     chart="kube2iam",
    #     repo="https://jtblin.github.io/kube2iam/",
    #     namespace="kube-system",
    #     version="2.6.0",
    #     values={
    #         # allow running kube2iam on control plane
    #         "tolerations": [
    #             {
    #                 "operator": "Exists",
    #                 "effect": "NoSchedule"
    #             }
    #         ],
    #
    #         "host": {
    #             "iptables": True,
    #             "interface": "eni+"
    #         },  # TODO: what happens if using cilium? - move this to the CNI?
    #     }
    # ),
    # because a picture is worth a thousand words
    HelmChart(
        chart="kubernetes-dashboard",
        repo="https://kubernetes.github.io/dashboard/",
        namespace="kube-system",
        version="4.0.0",
        values={
            # allow running kubernetes-dashboard on control plane
            "tolerations": [{"operator": "Exists", "effect": "NoSchedule"}]
        },
    ),
    HelmChart(
        chart="sealed-secrets",
        repo="https://bitnami-labs.github.io/sealed-secrets",
        namespace="kube-system",
        version="1.16.1",
        values={
            "commandArgs": ["--update-status"],
            "tolerations": [{"operator": "Exists", "effect": "NoSchedule"}],
        },
    ),
]


class Charts(ComponentResource):
    """
    Installs default Helm charts into the cluster
    """

    def __init__(self, name: str, extra_charts: list[HelmChart], opts: ResourceOptions = None):
        super().__init__(
            f"pkg:thunder:kubernetes:personalizers:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )

        # install default charts
        for chart in DEFAULT_CHARTS:
            HelmChartComponent(chart.chart, chart=chart, opts=ResourceOptions(parent=self))

        for chart in extra_charts:
            # install extra helm charts
            HelmChartComponent(chart.chart, chart=chart, opts=ResourceOptions(parent=self))
