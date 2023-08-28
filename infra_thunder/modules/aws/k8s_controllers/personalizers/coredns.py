from pulumi import ResourceOptions
from pulumi_kubernetes import provider as kubernetes_provider

from infra_thunder.lib.config import tag_namespace
from infra_thunder.lib.kubernetes.common.annotations.monitoring_annotations import (
    get_datadog_annotations,
)
from infra_thunder.lib.kubernetes.constants import DEDICATED_TAG_KEY
from infra_thunder.lib.kubernetes.helm import HelmChartStack
from infra_thunder.lib.kubernetes.helm.config import HelmChart
from ..config import K8sControllerArgs


def _patch_coredns_rbac(obj, opts):
    """
    This transformation function mutates the Helm chart for CoreDNS to add additional RBAC privileges
    """
    if obj["kind"] == "ClusterRole" and obj["metadata"]["name"] == "coredns":
        if obj["rules"][0]["apiGroups"][0] == "":
            obj["rules"][0]["resources"].append("nodes")


def configure_coredns(
    coredns_clusterip: str,
    provider: kubernetes_provider.Provider,
    cluster_config: K8sControllerArgs,
):
    """
    Configure CoreDNS in the cluster as a ClusterIP service, and pick the IP address to use for the DNS ClusterIP.
    By default the ClusterIP is the 10th host in the Service CIDR (10.24.240.10 if CIDR is 10.24.240.0/24).

    :param coredns_clusterip:
    :param provider:
    :param cluster_config:
    :return:
    """
    HelmChartStack(
        "coredns",
        namespace=cluster_config.name,
        chart=HelmChart(
            chart="coredns",
            repo="https://coredns.github.io/helm",
            version="1.16.5",
            namespace="kube-system",
            transformations=[_patch_coredns_rbac],
            values={
                # to prevent rendering service as 'coredns-coredns'
                "fullnameOverride": "coredns",
                # use custom image that includes node dns name support
                "image": {"repository": "public.ecr.aws/e5r9m0c5/coredns-kubenodes", "tag": "v1.8.6"},
                # enable the cluster-proportional autoscaler
                "autoscaler": {
                    "enabled": True,
                    # allow the autoscaler to run on any node
                    "tolerations": [{"operator": "Exists", "effect": "NoSchedule"}],
                    "resources": {
                        "requests": {
                            "cpu": "20m",
                            "memory": "16Mi",
                        },
                        "limits": {
                            "cpu": "20m",
                            "memory": "24Mi",
                        },
                    },
                },
                "resources": {
                    "requests": None,
                    "limits": {
                        "cpu": None,
                        "memory": "192Mi",
                    },
                },
                # set the ip address of the coredns service manually
                "service": {"clusterIP": coredns_clusterip},
                "priorityClassName": "system-cluster-critical",
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
                                "name": "kubenodes",
                                "parameters": f"node.{cluster_config.cluster_domain} node.cluster.local in-addr.arpa ip6.arpa",
                                "configBlock": "fallthrough in-addr.arpa ip6.arpa\nttl 30",
                            },
                            {
                                "name": "kubernetes",
                                # we add specific cluster domain name endpoints to allow cross-cluster access of services
                                "parameters": f"{cluster_config.cluster_domain} cluster.local in-addr.arpa ip6.arpa",
                                "configBlock": "pods insecure\nfallthrough in-addr.arpa ip6.arpa\nttl 30",
                            },
                            {"name": "prometheus", "parameters": "0.0.0.0:9153"},
                            {"name": "forward", "parameters": ". /etc/resolv.conf"},
                            {"name": "cache", "parameters": 30},
                            {"name": "loop"},
                            {"name": "reload"},
                            {"name": "loadbalance"},
                        ],
                    },
                    *[
                        {
                            "zones": [{"zone": f"{i.sysenv}.{tag_namespace}"}],
                            "port": 53,
                            "plugins": [
                                {
                                    "name": "forward",
                                    "parameters": f". {i.resolver}",
                                }
                            ],
                        }
                        for i in cluster_config.coredns_domains
                    ],
                ],
                # allow running coredns everywhere
                "tolerations": [{"operator": "Exists", "effect": "NoSchedule"}],
                "affinity": {
                    "nodeAffinity": {
                        "requiredDuringSchedulingIgnoredDuringExecution": {
                            "nodeSelectorTerms": [
                                # prefer not running coredns on dedicated nodes, as they might have workloads
                                # that would make coredns respond slowly
                                {
                                    "matchExpressions": [
                                        {
                                            "key": f"{tag_namespace}/{DEDICATED_TAG_KEY}",
                                            "operator": "DoesNotExist",
                                            "values": [],
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                },
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
        opts=ResourceOptions(parent=provider, provider=provider),
    )
