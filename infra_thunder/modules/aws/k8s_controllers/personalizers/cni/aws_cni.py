import json

from pulumi import ResourceOptions, Output, ComponentResource
from pulumi_aws import ec2
from pulumi_kubernetes import (
    provider as kubernetes_provider,
    core,
    meta,
    apiextensions,
    apps,
    rbac,
)

from infra_thunder.lib.kubernetes.common.annotations.monitoring_annotations import (
    get_datadog_annotations,
)
from infra_thunder.lib.kubernetes.helm import HelmChartStack
from infra_thunder.lib.kubernetes.helm.config import HelmChart
from infra_thunder.lib.security_groups import get_default_security_groups
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_tags
from ...config import K8sControllerArgs


def configure_cni(
    cls,
    endpoint: Output[str],
    pod_security_groups: list[ec2.SecurityGroup],
    k8s_provider: kubernetes_provider.Provider,
    cluster_config: K8sControllerArgs,
):
    # install kube-proxy first so the cni has access to the kube apiserver
    _install_kube_proxy(cls, endpoint, k8s_provider, cluster_config)
    # install the cni, and add the eniconfigs after the chart finishes installing
    cni_stack = _install_cni(cls, k8s_provider, cluster_config)
    _create_eniconfigs(cls, cni_stack, pod_security_groups, k8s_provider)


def _install_cni(cls, provider: kubernetes_provider.Provider, cluster_config: K8sControllerArgs):
    """
    Use Helm to install the AWS CNI and configure it with some sane defaults

    The CNI runs on the controllers via kubelet

    :param cls: Parent class
    :param provider: Pulumi Kubernetes provider
    :param cluster_config: Kubernetes Configuration
    :return:
    """
    return HelmChartStack(
        "aws-cni",
        namespace=cluster_config.name,
        chart=HelmChart(
            chart="aws-vpc-cni",
            repo="https://aws.github.io/eks-charts",
            version="1.1.10",
            namespace="kube-system",
            values={
                "image": {"region": cls.region},
                "env": {
                    # custom eni tags
                    "ADDITIONAL_ENI_TAGS": json.dumps(get_tags("k8s", "eni", cluster_config.name)),
                    # enable eniconfig support
                    "AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG": True,
                    # pod subnets have a NAT gateway attached, use that
                    "AWS_VPC_K8S_CNI_EXTERNALSNAT": True,
                    # use the eniconfig per AZ
                    "ENI_CONFIG_LABEL_DEF": "topology.kubernetes.io/zone",
                },
            },
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )


def _create_eniconfigs(
    cls,
    dependency: ComponentResource,
    pod_security_groups: list[ec2.SecurityGroup],
    provider: kubernetes_provider.Provider,
):
    """
    Create ENIConfig objcts for each availability zone

    :param cls: Parent class
    :param pod_security_groups: List of security groups to use for pods
    :param provider:
    :return:
    """
    pod_subnets = get_subnets_attributes(public=False, purpose="pods", vpc_id=cls.vpc.id)
    for subnet in pod_subnets:
        # Create ENIConfig per subnet
        apiextensions.CustomResource(
            f"eniconfig-{subnet.availability_zone}",
            api_version="crd.k8s.amazonaws.com/v1alpha1",
            metadata=meta.v1.ObjectMetaArgs(name=subnet.availability_zone),
            kind="ENIConfig",
            spec={
                "securityGroups": [sg.id for sg in pod_security_groups] + get_default_security_groups(cls.vpc.id).ids,
                "subnet": subnet.id,
            },
            # TODO: this doesn't wait for the CNI stack to complete?
            opts=ResourceOptions(parent=dependency, depends_on=[dependency], provider=provider),
        )


def _install_kube_proxy(
    cls,
    endpoint: Output[str],
    provider: kubernetes_provider.Provider,
    cluster_config: K8sControllerArgs,
):
    # add service account and rolebinding
    # Translation of https://github.com/kubernetes/kubernetes/blob/master/cluster/addons/kube-proxy/kube-proxy-rbac.yaml
    # ...with some modifications
    sa = core.v1.ServiceAccount(
        "kube-proxy",
        metadata=meta.v1.ObjectMetaArgs(
            name="kube-proxy",
            namespace="kube-system",
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )
    crb = rbac.v1.ClusterRoleBinding(
        "kube-proxy",
        metadata=meta.v1.ObjectMetaArgs(name="system:kube-proxy"),
        subjects=[rbac.v1.SubjectArgs(kind="ServiceAccount", name="kube-proxy", namespace="kube-system")],
        role_ref=rbac.v1.RoleRefArgs(
            kind="ClusterRole",
            name="system:node-proxier",
            api_group="rbac.authorization.k8s.io",
        ),
        opts=ResourceOptions(parent=sa, provider=provider),
    )

    # Translation of https://github.com/kubernetes/kubernetes/blob/master/cluster/addons/kube-proxy/kube-proxy-ds.yaml
    # ...with a few modifications (of course)
    apps.v1.DaemonSet(
        "kube-proxy",
        metadata=meta.v1.ObjectMetaArgs(
            labels={
                "k8s-app": "kube-proxy",
            },
            name="kube-proxy",
            namespace="kube-system",
        ),
        spec=apps.v1.DaemonSetSpecArgs(
            selector=meta.v1.LabelSelectorArgs(match_labels={"k8s-app": "kube-proxy"}),
            update_strategy=apps.v1.DaemonSetUpdateStrategyArgs(
                type="RollingUpdate",
                rolling_update=apps.v1.RollingUpdateDaemonSetArgs(max_unavailable="10%"),
            ),
            template=core.v1.PodTemplateSpecArgs(
                metadata=meta.v1.ObjectMetaArgs(
                    labels={"k8s-app": "kube-proxy"},
                    annotations=get_datadog_annotations(
                        "kube-proxy",
                        "kube_proxy",
                        {
                            # use localhost, kube-proxy runs in host networking mode and listens to localhost only
                            "prometheus_url": "http://127.0.0.1:10249/metrics"
                        },
                    ),
                ),
                spec=core.v1.PodSpecArgs(
                    priority_class_name="system-node-critical",
                    host_network=True,
                    node_selector={
                        "kubernetes.io/os": "linux",
                        # TODO: could add a magic label here to wait for kubelet to be ready
                    },
                    tolerations=[
                        core.v1.TolerationArgs(operator="Exists", effect="NoExecute"),
                        core.v1.TolerationArgs(operator="Exists", effect="NoSchedule"),
                    ],
                    containers=[
                        core.v1.ContainerArgs(
                            name="kube-proxy",
                            image="gcr.io/google_containers/kube-proxy-amd64:v1.20.0-alpha.0",  # TODO, bump this to higher version
                            resources=core.v1.ResourceRequirementsArgs(limits={"cpu": "0.1", "memory": "64Mi"}),
                            command=[
                                "/usr/local/bin/kube-proxy",
                                f"--cluster-cidr={cluster_config.service_cidr}",
                                "--oom-score-adj=-998",
                            ],
                            env=[
                                core.v1.EnvVarArgs(
                                    name="KUBERNETES_SERVICE_HOST",
                                    # This is set to the external endpoint of kube-apiserver
                                    # ClusterIP CIDR is handled by kube-proxy, so we must handle the chicken/egg issue here
                                    value=endpoint,
                                )
                            ],
                            security_context=core.v1.SecurityContextArgs(privileged=True),
                            volume_mounts=[
                                core.v1.VolumeMountArgs(
                                    name="varlog",
                                    mount_path="/var/log",
                                    read_only=False,
                                ),
                                core.v1.VolumeMountArgs(
                                    name="xtables-lock",
                                    mount_path="/run/xtables.lock",
                                    read_only=False,
                                ),
                                core.v1.VolumeMountArgs(
                                    name="lib-modules",
                                    mount_path="/lib/modules",
                                    read_only=True,
                                ),
                            ],
                        )
                    ],
                    volumes=[
                        core.v1.VolumeArgs(
                            name="varlog",
                            host_path=core.v1.HostPathVolumeSourceArgs(path="/var/log"),
                        ),
                        core.v1.VolumeArgs(
                            name="xtables-lock",
                            host_path=core.v1.HostPathVolumeSourceArgs(path="/run/xtables.lock", type="FileOrCreate"),
                        ),
                        core.v1.VolumeArgs(
                            name="lib-modules",
                            host_path=core.v1.HostPathVolumeSourceArgs(path="/lib/modules"),
                        ),
                    ],
                    service_account_name="kube-proxy",
                ),
            ),
        ),
        opts=ResourceOptions(parent=sa, depends_on=[sa, crb], provider=provider),
    )
