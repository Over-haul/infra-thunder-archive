from pulumi import ResourceOptions
from pulumi_aws import iam
from pulumi_kubernetes import provider as kubernetes_provider

from infra_thunder.lib.kubernetes.helm import HelmChartStack
from infra_thunder.lib.kubernetes.helm.config import HelmChart
from infra_thunder.lib.tags import get_tags
from ..config import K8sControllerArgs


def configure_aws_ebs_csi(
    provider: kubernetes_provider.Provider,
    ebs_controller_role: iam.Role,
    cluster_config: K8sControllerArgs,
):
    """
    Configure the AWS EBS CSI provider to allow creation of EBS volumes and attaching them to pods

    :param provider:
    :param ebs_controller_role:
    :param cluster_config:
    :return:
    """
    HelmChartStack(
        "aws-ebs-csi-driver",
        namespace=cluster_config.name,
        chart=HelmChart(
            chart="aws-ebs-csi-driver",
            repo="https://kubernetes-sigs.github.io/aws-ebs-csi-driver",
            version="1.2.4",
            namespace="kube-system",
            values={
                "enableVolumeResizing": True,
                "enableVolumeSnapshot": True,
                "enableVolumeScheduling": True,
                "extraVolumeTags": get_tags("k8s", "volume", cluster_config.name),
                "storageClasses": [
                    {
                        "name": "ebs-sc",
                        "volumeBindingMode": "WaitForFirstConsumer",
                        "allowVolumeExpansion": True,
                        "annotations": {"storageclass.kubernetes.io/is-default-class": "true"},
                    }
                ],
                "podAnnotations": {"iam.amazonaws.com/role": ebs_controller_role.arn},
                "resources": {
                    "limits": {
                        "memory": "64Mi",
                    }
                },
                # these tolerations are for snapshot controller
                "tolerations": [
                    {
                        "key": "node-role.kubernetes.io/control-plane",
                        "operator": "Exists",
                        "effect": "NoSchedule",
                    },
                    {
                        "key": "node-role.kubernetes.io/master",
                        "operator": "Exists",
                        "effect": "NoSchedule",
                    },
                ],
                # these selectors are for the snapshot controller
                "nodeSelector": {"node-role.kubernetes.io/control-plane": ""},
                # configuration for the controller only
                "controller": {
                    "tolerations": [
                        # controller should only tolerate running on the control plane
                        # (and 'master', even though that taint is deprecated)
                        {
                            "key": "node-role.kubernetes.io/control-plane",
                            "operator": "Exists",
                            "effect": "NoSchedule",
                        },
                        {
                            "key": "node-role.kubernetes.io/master",
                            "operator": "Exists",
                            "effect": "NoSchedule",
                        },
                    ],
                    "nodeSelector": {"node-role.kubernetes.io/control-plane": ""},
                    "resources": {
                        "limits": {
                            "memory": "64Mi",
                        }
                    },
                },
                # configuration for the node driver (should run everywhere)
                "node": {
                    # node needs to run everywhere, no matter what.
                    "tolerateAllTaints": True,
                    "resources": {"limits": {"memory": "64Mi"}},
                },
            },
            skip_crd_rendering=True,
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )
