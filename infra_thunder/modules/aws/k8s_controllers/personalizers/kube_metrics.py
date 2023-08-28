import pulumi_kubernetes as kubernetes

from pulumi import ResourceOptions


def configure_kube_metrics(provider: kubernetes.Provider):
    name = "metrics-server"
    ns = "kube-system"
    sa = kubernetes.core.v1.ServiceAccount(
        "metrics-sa",
        api_version="v1",
        kind="ServiceAccount",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            labels={
                "k8s-app": name,
            },
            name=name,
            namespace=ns,
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )
    kubernetes.rbac.v1.ClusterRole(
        "metrics-reader-role",
        api_version="rbac.authorization.k8s.io/v1",
        kind="ClusterRole",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            labels={
                "k8s-app": name,
                "rbac.authorization.k8s.io/aggregate-to-admin": "true",
                "rbac.authorization.k8s.io/aggregate-to-edit": "true",
                "rbac.authorization.k8s.io/aggregate-to-view": "true",
            },
            name="system:aggregated-metrics-reader",
        ),
        rules=[
            kubernetes.rbac.v1.PolicyRuleArgs(
                api_groups=["metrics.k8s.io"],
                resources=[
                    "pods",
                    "nodes",
                ],
                verbs=[
                    "get",
                    "list",
                    "watch",
                ],
            )
        ],
        opts=ResourceOptions(parent=sa, provider=provider),
    )
    kubernetes.rbac.v1.ClusterRole(
        "metrics-server-role",
        api_version="rbac.authorization.k8s.io/v1",
        kind="ClusterRole",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            labels={
                "k8s-app": name,
            },
            name="system:metrics-server",
        ),
        rules=[
            kubernetes.rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=[
                    "pods",
                    "nodes",
                    "nodes/stats",
                    "namespaces",
                    "configmaps",
                ],
                verbs=[
                    "get",
                    "list",
                    "watch",
                ],
            )
        ],
        opts=ResourceOptions(parent=sa, provider=provider),
    )
    kubernetes.rbac.v1.RoleBinding(
        "metrics-server-reader-rb",
        api_version="rbac.authorization.k8s.io/v1",
        kind="RoleBinding",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            labels={
                "k8s-app": name,
            },
            name="metrics-server-auth-reader",
            namespace=ns,
        ),
        role_ref=kubernetes.rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="Role",
            name="extension-apiserver-authentication-reader",
        ),
        subjects=[
            kubernetes.rbac.v1.SubjectArgs(
                kind="ServiceAccount",
                name=name,
                namespace=ns,
            )
        ],
        opts=ResourceOptions(parent=sa, provider=provider),
    )
    kubernetes.rbac.v1.ClusterRoleBinding(
        "metrics-server-auth-delegator-crb",
        api_version="rbac.authorization.k8s.io/v1",
        kind="ClusterRoleBinding",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            labels={
                "k8s-app": name,
            },
            name="metrics-server:system:auth-delegator",
        ),
        role_ref=kubernetes.rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name="system:auth-delegator",
        ),
        subjects=[
            kubernetes.rbac.v1.SubjectArgs(
                kind="ServiceAccount",
                name=name,
                namespace=ns,
            )
        ],
        opts=ResourceOptions(parent=sa, provider=provider),
    )
    kubernetes.rbac.v1.ClusterRoleBinding(
        "metrics-server-crb",
        api_version="rbac.authorization.k8s.io/v1",
        kind="ClusterRoleBinding",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            labels={
                "k8s-app": name,
            },
            name="system:metrics-server",
        ),
        role_ref=kubernetes.rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name="system:metrics-server",
        ),
        subjects=[
            kubernetes.rbac.v1.SubjectArgs(
                kind="ServiceAccount",
                name=name,
                namespace=ns,
            )
        ],
        opts=ResourceOptions(parent=sa, provider=provider),
    )
    kubernetes.core.v1.Service(
        "metrics-server-svc",
        api_version="v1",
        kind="Service",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            labels={
                "k8s-app": name,
            },
            annotations={"pulumi.com/skipAwait": "true"},
            name=name,
            namespace=ns,
        ),
        spec=kubernetes.core.v1.ServiceSpecArgs(
            ports=[
                kubernetes.core.v1.ServicePortArgs(
                    name="https",
                    port=443,
                    protocol="TCP",
                    target_port="https",
                )
            ],
            selector={
                "k8s-app": name,
            },
        ),
        opts=ResourceOptions(parent=sa, provider=provider),
    )
    kubernetes.apps.v1.Deployment(
        "metrics-server-deployment",
        api_version="apps/v1",
        kind="Deployment",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            labels={
                "k8s-app": name,
            },
            annotations={"pulumi.com/skipAwait": "true"},
            name=name,
            namespace=ns,
        ),
        spec=kubernetes.apps.v1.DeploymentSpecArgs(
            selector=kubernetes.meta.v1.LabelSelectorArgs(
                match_labels={
                    "k8s-app": name,
                },
            ),
            strategy=kubernetes.apps.v1.DeploymentStrategyArgs(
                rolling_update={
                    "max_unavailable": 0,
                },
            ),
            template=kubernetes.core.v1.PodTemplateSpecArgs(
                metadata=kubernetes.meta.v1.ObjectMetaArgs(
                    labels={
                        "k8s-app": name,
                    },
                ),
                spec=kubernetes.core.v1.PodSpecArgs(
                    containers=[
                        kubernetes.core.v1.ContainerArgs(
                            args=[
                                "--cert-dir=/tmp",
                                "--secure-port=443",
                                "--kubelet-preferred-address-types=InternalIP,ExternalIP,Hostname",
                                "--kubelet-use-node-status-port",
                                "--metric-resolution=15s",
                            ],
                            image="k8s.gcr.io/metrics-server/metrics-server:v0.5.0",
                            image_pull_policy="IfNotPresent",
                            liveness_probe={
                                "failure_threshold": 3,
                                "http_get": {
                                    "path": "/livez",
                                    "port": "https",
                                    "scheme": "HTTPS",
                                },
                                "period_seconds": 10,
                            },
                            name=name,
                            ports=[
                                kubernetes.core.v1.ContainerPortArgs(
                                    container_port=443,
                                    name="https",
                                    protocol="TCP",
                                )
                            ],
                            readiness_probe={
                                "failure_threshold": 3,
                                "http_get": {
                                    "path": "/readyz",
                                    "port": "https",
                                    "scheme": "HTTPS",
                                },
                                "initial_delay_seconds": 20,
                                "period_seconds": 10,
                            },
                            resources=kubernetes.core.v1.ResourceRequirementsArgs(
                                requests={
                                    "cpu": "100m",
                                    "memory": "200Mi",
                                },
                            ),
                            security_context={
                                "read_only_root_filesystem": True,
                                "run_as_non_root": True,
                                "run_as_user": 1000,
                            },
                            volume_mounts=[
                                {
                                    "mount_path": "/tmp",
                                    "name": "tmp-dir",
                                }
                            ],
                        )
                    ],
                    node_selector={
                        "kubernetes.io/os": "linux",
                    },
                    tolerations=[kubernetes.core.v1.TolerationArgs(operator="Exists", effect="NoSchedule")],
                    priority_class_name="system-cluster-critical",
                    service_account_name=name,
                    volumes=[
                        kubernetes.core.v1.VolumeArgs(
                            empty_dir={},
                            name="tmp-dir",
                        )
                    ],
                ),
            ),
        ),
        opts=ResourceOptions(parent=sa, provider=provider),
    )
    kubernetes.apiregistration.v1.APIService(
        "metrics-server-apiservice",
        api_version="apiregistration.k8s.io/v1",
        kind="APIService",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            labels={
                "k8s-app": name,
            },
            name="v1beta1.metrics.k8s.io",
        ),
        spec=kubernetes.apiregistration.v1.APIServiceSpecArgs(
            group="metrics.k8s.io",
            group_priority_minimum=100,
            insecure_skip_tls_verify=True,
            service=kubernetes.apiregistration.v1.ServiceReferenceArgs(
                name=name,
                namespace=ns,
            ),
            version="v1beta1",
            version_priority=100,
        ),
        opts=ResourceOptions(parent=sa, provider=provider),
    )
