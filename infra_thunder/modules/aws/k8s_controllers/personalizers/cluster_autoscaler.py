from pulumi import ResourceOptions
from pulumi_aws import iam
from yaml import safe_dump
from pulumi_kubernetes import meta, core
from pulumi_kubernetes import provider as kubernetes_provider

from infra_thunder.lib.config import tag_prefix
from infra_thunder.lib.kubernetes.common.annotations.monitoring_annotations import (
    get_datadog_annotations,
)
from infra_thunder.lib.kubernetes.helm import HelmChartStack
from infra_thunder.lib.kubernetes.helm.config import HelmChart
from ..config import K8sControllerArgs


def configure_cluster_autoscaler(
    provider: kubernetes_provider.Provider,
    cluster_autoscaler_role: iam.Role,
    cluster_config: K8sControllerArgs,
    region: str,
):
    """
    Configure the cluster autoscaler

    :param provider:
    :param cluster_autoscaler_role:
    :param cluster_config:
    :param region:
    :return:
    """
    cluster_autoscaler_priorities = {10: [".*"]}
    _create_autoscaler_priority_config_map(provider, cluster_autoscaler_priorities)

    HelmChartStack(
        "cluster-autoscaler",
        namespace=cluster_config.name,
        chart=HelmChart(
            chart="cluster-autoscaler",
            repo="https://kubernetes.github.io/autoscaler",
            version="9.18.1",
            namespace="kube-system",
            values={
                "fullnameOverride": "cluster-autoscaler",
                "cloudProvider": "aws",
                "awsRegion": region,
                "resources": {
                    "limits": {
                        "memory": "256Mi",
                    },
                },
                "autoDiscovery": {
                    "tags": [
                        f"{tag_prefix}service=k8s-agents",
                        f"{tag_prefix}role={cluster_config.name}",
                    ],
                    # honestly just seems to be used as a boolean, https://github.com/kubernetes/autoscaler/blob/49118e2edc8c59bf8ba6e69fedf271a51b68fc23/charts/cluster-autoscaler/templates/deployment.yaml#L56
                    "clusterName": cluster_config.name,
                },
                "tolerations": [
                    {
                        "operator": "Exists",
                        "effect": "NoSchedule",
                    }
                ],
                "nodeSelector": {
                    "node-role.kubernetes.io/control-plane": "",
                },
                "podAnnotations": {
                    "iam.amazonaws.com/role": cluster_autoscaler_role.arn,
                    **get_datadog_annotations(
                        "aws-cluster-autoscaler",
                        "openmetrics",
                        {
                            "openmetrics_endpoint": "http://%%host%%:8085/metrics",
                            "namespace": "kubernetes.cluster-autoscaler",
                            "raw_metric_prefix": "cluster_autoscaler_",
                            "metrics": [".*"],
                        },
                    ),
                },
                # TODO: remove this image arg when `tag` semver is ^v1.24.0
                # here https://github.com/kubernetes/autoscaler/blob/master/charts/cluster-autoscaler/values.yaml#L235
                "image": {
                    "tag": "v1.24.0",
                },
                "extraArgs": {
                    "expander": "priority",
                },
            },
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )


def _create_autoscaler_priority_config_map(provider: kubernetes_provider.Provider, priorities: dict[int]):
    """
    Priority based expander for cluster-autoscaler
    Docs https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler/expander/priority
    :param provider:
    :param priorities:
        10: [
          ".*t2\\.large.*",
          ".*t3\\.large.*"
        ],
        50: [...]
    """
    return core.v1.ConfigMap(
        "cluster-autoscaler-priority-expander",
        metadata=meta.v1.ObjectMetaArgs(name="cluster-autoscaler-priority-expander", namespace="kube-system"),
        data={"priorities": safe_dump(priorities)},
        opts=ResourceOptions(parent=provider, provider=provider),
    )
