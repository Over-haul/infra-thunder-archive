from pulumi import Output
from pulumi_aws import ec2
from pulumi_kubernetes import provider as kubernetes_provider

from .aws_cni import configure_cni as configure_aws_cni
from ...config import K8sControllerArgs
from ...types import CNIProviders


# from .cilium import configure_cni as configure_cilium_cni


def configure_cni(
    cls,
    endpoint: Output[str],
    pod_security_groups: list[ec2.SecurityGroup],
    k8s_provider: kubernetes_provider.Provider,
    cluster_config: K8sControllerArgs,
):
    """
    Configure the selected CNI against the Kubernetes cluster
    :param cls: Parent class
    :param pod_security_groups: Pod security groups
    :param k8s_provider: Kubernetes provider
    :param cluster_config: Kubernetes Cluster Configuration
    :return:
    """
    cni_funcs = {CNIProviders.aws_cni.value: configure_aws_cni}
    cni_func = cni_funcs[cluster_config.cni_provider]

    # Launch the configure func
    cni_func(cls, endpoint, pod_security_groups, k8s_provider, cluster_config)
