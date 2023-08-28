from pulumi import ResourceOptions
from pulumi_kubernetes import core, rbac, meta, apiregistration, apps
from pulumi_kubernetes import provider as kubernetes_provider

from .monitoring_roles import CONTROLLER_MONITORING_SA
from ..config import K8sControllerArgs

CLUSTER_AGENT_NAME = "datadog-cluster-agent"
CLUSTER_AGENT_NAMESPACE = "kube-system"
CLUSTER_AGENT_METRICS_PORT = 8443
CLUSTER_AGENT_AGENT_PORT = 5005
CLUSTER_AGENT_ADMISSION_PORT = 8000


def configure_datadog_cluster_agent(provider: kubernetes_provider.Provider, cluster_config: K8sControllerArgs):
    """
    Installs the Datadog Cluster Agent into the cluster.
    It is responsible for providing the ExternalMetrics to the cluster for HPA as an Aggregated API Server,
    much like how kube-metrics-server functions.

    This requires the monitoring roles to be set up first, since the DD cluster agent requires them to function.
    """
    _configure_datadog_cluster_agent_deployment(provider, cluster_config)
    _configure_datadog_cluster_agent_rbac(provider)
    _configure_datadog_cluster_agent_services(provider)


def _configure_datadog_cluster_agent_deployment(
    provider: kubernetes_provider.Provider, cluster_config: K8sControllerArgs
):
    apps.v1.Deployment(
        CLUSTER_AGENT_NAME,
        api_version="apps/v1",
        kind="Deployment",
        metadata=meta.v1.ObjectMetaArgs(
            namespace=CLUSTER_AGENT_NAMESPACE,
            name=CLUSTER_AGENT_NAME,
            annotations={
                "pulumi.com/skipAwait": "true",
            },
            labels={
                "app.kubernetes.io/name": CLUSTER_AGENT_NAME,
            },
        ),
        spec=apps.v1.DeploymentSpecArgs(
            replicas=1,
            selector=meta.v1.LabelSelectorArgs(
                match_labels={
                    "app.kubernetes.io/name": CLUSTER_AGENT_NAME,
                },
            ),
            template=core.v1.PodTemplateSpecArgs(
                metadata=meta.v1.ObjectMetaArgs(
                    labels={
                        "app.kubernetes.io/name": CLUSTER_AGENT_NAME,
                    },
                ),
                spec=core.v1.PodSpecArgs(
                    service_account_name=CONTROLLER_MONITORING_SA,
                    tolerations=[
                        core.v1.TolerationArgs(
                            operator="Exists",
                            key="node-role.kubernetes.io/control-plane",
                            effect="NoSchedule",
                        ),
                        core.v1.TolerationArgs(
                            operator="Exists",
                            key="node-role.kubernetes.io/master",
                            effect="NoSchedule",
                        ),
                    ],
                    containers=[
                        core.v1.ContainerArgs(
                            name=CLUSTER_AGENT_NAME,
                            image="datadog/cluster-agent:1.18.0",
                            ports=[
                                core.v1.ContainerPortArgs(
                                    container_port=CLUSTER_AGENT_AGENT_PORT,
                                    name="agentport",
                                    protocol="TCP",
                                ),
                                core.v1.ContainerPortArgs(
                                    container_port=CLUSTER_AGENT_METRICS_PORT,
                                    name="metricsapi",
                                    protocol="TCP",
                                ),
                                core.v1.ContainerPortArgs(
                                    container_port=CLUSTER_AGENT_ADMISSION_PORT,
                                    name="admission",
                                    protocol="TCP",
                                ),
                            ],
                            env=[
                                core.v1.EnvVarArgs(
                                    name="DD_CLUSTER_NAME",
                                    value=cluster_config.name,
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_API_KEY",
                                    value_from=core.v1.EnvVarSourceArgs(
                                        secret_key_ref=core.v1.SecretKeySelectorArgs(name="datadog", key="api-key")
                                    ),
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_APP_KEY",
                                    value_from=core.v1.EnvVarSourceArgs(
                                        secret_key_ref=core.v1.SecretKeySelectorArgs(name="datadog", key="app-key")
                                    ),
                                ),
                                core.v1.EnvVarArgs(
                                    name="KUBERNETES",
                                    value="yes",
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_EXTERNAL_METRICS_PROVIDER_ENABLED",
                                    value="true",
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_EXTERNAL_METRICS_PROVIDER_PORT",
                                    value=str(CLUSTER_AGENT_METRICS_PORT),
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_EXTERNAL_METRICS_PROVIDER_WPA_CONTROLLER",
                                    value="false",
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_EXTERNAL_METRICS_PROVIDER_BUCKET_SIZE",
                                    value="1800",
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_EXTERNAL_METRICS_PROVIDER_MAX_AGE",
                                    value="600",
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_ADMISSION_CONTROLLER_ENABLED",
                                    value="true",
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_ADMISSION_CONTROLLER_MUTATE_UNLABELLED",
                                    value="false",
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_ADMISSION_CONTROLLER_SERVICE_NAME",
                                    value=f"{CLUSTER_AGENT_NAME}-admission-controller",
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_CLUSTER_CHECKS_ENABLED",
                                    value="false",
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_CLUSTER_AGENT_KUBERNETES_SERVICE_NAME",
                                    value=CLUSTER_AGENT_NAME,
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_COLLECT_KUBERNETES_EVENTS",
                                    value="false",
                                ),
                                core.v1.EnvVarArgs(
                                    name="DD_LEADER_ELECTION",
                                    value="true",
                                ),
                            ],
                        )
                    ],
                ),
            ),
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )


def _configure_datadog_cluster_agent_rbac(provider: kubernetes_provider.Provider):
    metrics_reader_role = rbac.v1.ClusterRole(
        f"{CLUSTER_AGENT_NAME}-externalmetrics",
        api_version="rbac.authorization.k8s.io/v1",
        kind="ClusterRole",
        metadata=meta.v1.ObjectMetaArgs(
            name=f"{CLUSTER_AGENT_NAME}-external-metrics-reader",
        ),
        rules=[
            rbac.v1.PolicyRuleArgs(
                api_groups=["external.metrics.k8s.io"],
                resources=["*"],
                verbs=[
                    "list",
                    "get",
                    "watch",
                ],
            )
        ],
        opts=ResourceOptions(parent=provider, provider=provider),
    )

    rbac.v1.ClusterRoleBinding(
        f"{CLUSTER_AGENT_NAME}-externalmetrics",
        api_version="rbac.authorization.k8s.io/v1",
        kind="ClusterRoleBinding",
        metadata=meta.v1.ObjectMetaArgs(
            name=f"{CLUSTER_AGENT_NAME}-external-metrics-reader",
        ),
        role_ref=rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name=metrics_reader_role.metadata.name,
        ),
        subjects=[
            rbac.v1.SubjectArgs(
                kind="ServiceAccount",
                name="horizontal-pod-autoscaler",
                namespace="kube-system",
            )
        ],
        opts=ResourceOptions(parent=metrics_reader_role, provider=provider),
    )


def _configure_datadog_cluster_agent_services(provider: kubernetes_provider.Provider):
    external_metrics_service = core.v1.Service(
        f"{CLUSTER_AGENT_NAME}-externalmetrics",
        api_version="v1",
        kind="Service",
        metadata=meta.v1.ObjectMetaArgs(
            name=f"{CLUSTER_AGENT_NAME}-metrics-api",
            namespace=CLUSTER_AGENT_NAMESPACE,
            labels={
                "app.kubernetes.io/name": CLUSTER_AGENT_NAME,
            },
        ),
        spec=core.v1.ServiceSpecArgs(
            type="ClusterIP",
            selector={
                "app.kubernetes.io/name": CLUSTER_AGENT_NAME,
            },
            ports=[
                core.v1.ServicePortArgs(
                    port=CLUSTER_AGENT_METRICS_PORT,
                    name="metricsapi",
                    protocol="TCP",
                )
            ],
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )
    core.v1.Service(
        f"{CLUSTER_AGENT_NAME}-admission-controller",
        api_version="v1",
        kind="Service",
        metadata=meta.v1.ObjectMetaArgs(
            name=f"{CLUSTER_AGENT_NAME}-admission-controller",
            namespace=CLUSTER_AGENT_NAMESPACE,
            labels={
                "app.kubernetes.io/name": CLUSTER_AGENT_NAME,
            },
        ),
        spec=core.v1.ServiceSpecArgs(
            selector={
                "app.kubernetes.io/name": CLUSTER_AGENT_NAME,
            },
            ports=[
                core.v1.ServicePortArgs(
                    port=CLUSTER_AGENT_METRICS_PORT,
                    name="admission",
                )
            ],
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )

    apiregistration.v1.APIService(
        f"{CLUSTER_AGENT_NAME}-externalmetrics",
        api_version="apiregistration.k8s.io/v1",
        kind="APIService",
        metadata=meta.v1.ObjectMetaArgs(
            name="v1beta1.external.metrics.k8s.io",
        ),
        spec=apiregistration.v1.APIServiceSpecArgs(
            service=apiregistration.v1.ServiceReferenceArgs(
                name=external_metrics_service.metadata.name,
                namespace=CLUSTER_AGENT_NAMESPACE,
                port=CLUSTER_AGENT_METRICS_PORT,
            ),
            version="v1beta1",
            insecure_skip_tls_verify=True,
            group="external.metrics.k8s.io",
            group_priority_minimum=100,
            version_priority=100,
        ),
        opts=ResourceOptions(parent=external_metrics_service, provider=provider),
    )
