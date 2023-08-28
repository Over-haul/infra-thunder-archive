from pulumi import ResourceOptions, Output
from pulumi_aws import ec2
from pulumi_kubernetes import provider as kubernetes_provider

from infra_thunder.lib.kubernetes.helm import HelmChartStack
from infra_thunder.lib.kubernetes.helm.config import HelmChart
from ...config import K8sControllerArgs


def configure_cni(
    cls,
    endpoint: Output[str],
    pod_security_groups: list[ec2.SecurityGroup],
    k8s_provider: kubernetes_provider.Provider,
    cluster_config: K8sControllerArgs,
):
    _install_cni(cls, k8s_provider, cluster_config)


def _install_cni(cls, provider: kubernetes_provider.Provider, cluster_config: K8sControllerArgs):
    """
    Use Helm to install Cilium and configure it with some sane defaults

    :param cls: Parent class
    :param k8s_provider: Pulumi Kubernetes provider
    :param cluster_config: Kubernetes Configuration
    :return:
    """
    HelmChartStack(
        "aws-cni",
        namespace=cluster_config.name,
        chart=HelmChart(
            chart="cilium",
            repo="https://helm.cilium.io/",
            version="1.9.0",
            namespace="kube-system",
            values={
                "eni": "true",
                "ipam.mode": "eni",
                "egressMasqueradeInterfaces": "eth0",
                "tunnel": "disabled",
                "nodeinit.enabled": "true"
                # "hostreachableservices"??
                # default security groups??
                # default subnets
                # cluster name??
            },
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )
