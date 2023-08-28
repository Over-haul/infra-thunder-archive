from pulumi import ResourceOptions, ComponentResource

from infra_thunder.lib.kubernetes.common.annotations.monitoring_annotations import (
    get_datadog_annotations,
)
from infra_thunder.lib.kubernetes.helm import HelmChartComponent
from infra_thunder.lib.kubernetes.helm.config import HelmChart


class CoreDNS(ComponentResource):
    """
    Configure CoreDNS in the cluster as a ClusterIP service, and pick the IP address to use for the DNS ClusterIP.
    By default the ClusterIP is the 10th host in the Service CIDR (10.24.240.10 if CIDR is 10.24.240.0/24).
    """

    def __init__(
        self,
        name: str,
        coredns_clusterip: str,
        cluster_domain: str,
        opts: ResourceOptions = None,
    ):
        super().__init__(
            f"pkg:thunder:kubernetes:personalizers:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )

        HelmChartComponent(
            "coredns",
            chart=HelmChart(
                chart="coredns",
                repo="https://coredns.github.io/helm",
                version="1.14.1",
                namespace="kube-system",
                values={
                    # to prevent rendering service as 'coredns-coredns'
                    "fullnameOverride": "coredns",
                    # enable the cluster-proportional autoscaler
                    "autoscaler": {"enabled": True},
                    # set the ip address of the coredns service manually
                    "service": {"clusterIP": coredns_clusterip},
                    # "I'm gonna regret this" - Tyler 2021
                    "servers": [
                        {
                            "zones": [{"zone": "."}],
                            "port": 53,
                            "plugins": [
                                {"name": "errors"},
                                {"name": "health", "configBlock": "lameduck 5s"},
                                {"name": "ready"},
                                {
                                    "name": "kubernetes",
                                    # we add specific cluster domain name endpoints to allow cross-cluster access of services
                                    "parameters": f"{cluster_domain} cluster.local in-addr.arpa ip6.arpa",
                                    "configBlock": "pods insecure\nfallthrough in-addr.arpa ip6.arpa\nttl 30",
                                },
                                {"name": "prometheus", "parameters": "0.0.0.0:9153"},
                                {"name": "forward", "parameters": ". /etc/resolv.conf"},
                                {"name": "cache", "parameters": 30},
                                {"name": "loop"},
                                {"name": "reload"},
                                {"name": "loadbalance"},
                            ],
                        }
                    ],
                    # allow running coredns on control plane
                    "tolerations": [{"operator": "Exists", "effect": "NoSchedule"}],
                    # enable metrics
                    "prometheus": {
                        "service": {
                            "enabled": True,
                            # "annotations": {}
                        }
                    },
                    "podAnnotations": get_datadog_annotations(
                        "coredns",
                        "coredns",
                        {"prometheus_url": "http://%%host%%:9153/metrics"},
                    ),
                },
            ),
            opts=ResourceOptions(parent=self),
        )
