from pulumi import ResourceOptions
from pulumi_kubernetes import core, rbac, meta
from pulumi_kubernetes import provider as kubernetes_provider

from infra_thunder.lib.kubernetes.constants import MONITORING_SECRET_NAME

CONTROLLER_MONITORING_SA = "thunder-controller-monitoring"


def configure_monitoring_roles(provider: kubernetes_provider.Provider):
    """
    Configure monitoring roles for the controllers and nodes
    """
    _configure_controller_monitoring(provider)
    _configure_node_monitoring(provider)


def _configure_controller_monitoring(provider: kubernetes_provider.Provider):
    """
    Configure the monitoring role for the controllers

    The controller monitoring service is granted access to the role via a TLS certificate with the appropriate CN/O
    fields set to place the connection into the appropriate group that grants access to the role itself.
    The controller monitoring role has access to:
    - Read all information about:
        - Services
        - Endpoints
        - Pods
        - Namespaces
        - Component Statuses
    - Health status for all control plane components
    - Elect a leader via a configmap (TODO: figure out how to switch this to a Lease object)
    - Publish the datadog api key as a secret

    """
    # manually configure secret for node-based agents so we can use a predictable name
    controller_monitoring_sa = core.v1.ServiceAccount(
        "controller-monitoring-serviceaccount",
        metadata=meta.v1.ObjectMetaArgs(name=CONTROLLER_MONITORING_SA, namespace="kube-system"),
        opts=ResourceOptions(parent=provider, provider=provider),
    )

    # configure role for controller-based agents - this role has more permission than a normal node has
    controller_monitoring_role = rbac.v1.ClusterRole(
        "controller-monitoring-role",
        # api_version="rbac.authorization.k8s.io/v1",
        metadata=meta.v1.ObjectMetaArgs(
            name="thunder:controller-monitoring",
        ),
        rules=[
            rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=[
                    "services",
                    "limitranges",
                    "persistentvolumeclaims",
                    "persistentvolumes",
                    "replicationcontrollers",
                    "resourcequotas",
                    "secrets",
                    "events",
                    "endpoints",
                    "pods",
                    "nodes",
                    "namespaces",
                    "componentstatuses",
                ],
                verbs=[
                    "get",
                    "list",
                    "watch",
                ],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=["events"],
                verbs=["*"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=["extensions"],
                resources=[
                    "daemonsets",
                    "deployments",
                    "replicasets",
                ],
                verbs=["list", "watch"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=["apps"],
                resources=[
                    "statefulsets",
                    "daemonsets",
                    "deployments",
                    "replicasets",
                ],
                verbs=["list", "watch"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=["batch"],
                resources=[
                    "cronjobs",
                    "jobs",
                ],
                verbs=["list", "watch"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=["autoscaling"],
                resources=[
                    "horizontalpodautoscalers",
                ],
                verbs=["list", "watch"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=["policy"],
                resources=[
                    "poddisruptionbudgets",
                ],
                verbs=["list", "watch"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=["storage.k8s.io"],
                resources=[
                    "storageclasses",
                    "volumeattachments",
                ],
                verbs=["list", "watch"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=["admissionregistration.k8s.io"],
                resources=["mutatingwebhookconfigurations"],
                verbs=["get", "list", "watch", "update", "create"],
            ),
            # allow creation of secrets, but only allow retrieving specific ones
            # this rule also allows listing/watching them for changes for KSMv2_core
            rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=["secrets"],
                verbs=["create", "list", "watch"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=["secrets"],
                resource_names=[
                    "datadog",
                    "webhook-certificate",
                ],
                verbs=["get", "update", "patch"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=["configmaps"],
                verbs=["create"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=["configmaps"],
                # from https://github.com/DataDog/datadog-agent/blob/0454961e636342c9fbab9e561e6346ae804679a9/pkg/util/kubernetes/apiserver/leaderelection/leaderelection.go#L36
                resource_names=[
                    "datadog-leader-election",
                    "datadogtoken",
                    "datadog-custom-metrics",
                ],
                verbs=[
                    "get",
                    "update",
                ],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=["authorization.k8s.io"],
                resources=["subjectaccessreviews"],
                verbs=["*"],
            ),
            rbac.v1.PolicyRuleArgs(
                non_resource_urls=[
                    "/version",
                    "/healthz",
                ],
                verbs=["get"],
            ),
            rbac.v1.PolicyRuleArgs(
                non_resource_urls=["/metrics"],
                verbs=["get"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=[
                    "nodes/metrics",
                    "nodes/spec",
                    "nodes/proxy",
                    "nodes/stats",
                ],
                verbs=["get"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=["coordination.k8s.io"],
                resources=["leases"],
                verbs=["get", "create"],
            ),
        ],
        opts=ResourceOptions(parent=provider, provider=provider),
    )

    # configure crb for controller-based agents - no need to make a service account here since we'll issue a cert
    # directly into the role on the controller itself (since it has the CA anyway)
    rbac.v1.ClusterRoleBinding(
        "controller-monitoring-rolebinding",
        # api_version="rbac.authorization.k8s.io/v1",
        metadata=meta.v1.ObjectMetaArgs(
            name="thunder:controller-monitoring",
        ),
        subjects=[
            rbac.v1.SubjectArgs(
                kind="Group",
                api_group="rbac.authorization.k8s.io",
                name="thunder:controller-monitoring",
            ),
            rbac.v1.SubjectArgs(
                kind="ServiceAccount",
                name=controller_monitoring_sa.metadata.name,
                namespace=controller_monitoring_sa.metadata.namespace,
            ),
        ],
        role_ref=rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name=controller_monitoring_role.metadata.name,
        ),
        opts=ResourceOptions(parent=controller_monitoring_role, provider=provider),
    )
    # allow the dd cluster agent to act as a cluster extension apiserver (aggregated api)
    rbac.v1.RoleBinding(
        "controller-monitoring-extension-apiserver-rolebinding",
        metadata=meta.v1.ObjectMetaArgs(
            name="thunder:controller-monitoring-extension-apiserver",
            namespace="kube-system",
        ),
        subjects=[
            rbac.v1.SubjectArgs(
                kind="ServiceAccount",
                name=controller_monitoring_sa.metadata.name,
                namespace=controller_monitoring_sa.metadata.namespace,
            )
        ],
        role_ref=rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="Role",
            name="extension-apiserver-authentication-reader",
        ),
        opts=ResourceOptions(parent=controller_monitoring_role, provider=provider),
    )


def _configure_node_monitoring(provider: kubernetes_provider.Provider):
    """
    Configure the monitoring role for the node agents

    The node monitoring service is granted access to the role via a different mechanism.
    Kubelets are placed into the `system:bootstrappers` group, which grants access to read the MONITORING_SECRET,
    which is a service account token that lives in the `kube-system` namespace.

    When a node monitoring agent starts, it first retrieves the token by issuing
        `kubectl --kubeconfig kubelet.kubeconfig get secret ${MONITORING_SECRET}`
    Once the secret is obtained, the monitoring agent has access to assume the role granted by the node monitoring
    service account.

    The node monitoring role is granted permission to:
        - Read all information about:
            - Pods on this local kubelet
            -
    """
    # manually configure secret for node-based agents so we can use a predictable name
    node_monitoring_sa = core.v1.ServiceAccount(
        "node-monitoring-serviceaccount",
        metadata=meta.v1.ObjectMetaArgs(name="thunder-node-monitoring", namespace="kube-system"),
        secrets=[core.v1.SecretReferenceArgs(name=MONITORING_SECRET_NAME, namespace="kube-system")],
        opts=ResourceOptions(parent=provider, provider=provider),
    )

    # configure service account for node-based agents
    core.v1.Secret(
        "node-monitoring-secret",
        metadata=meta.v1.ObjectMetaArgs(
            name=MONITORING_SECRET_NAME,
            namespace="kube-system",
            annotations={
                "kubernetes.io/service-account.name": node_monitoring_sa.metadata.name,
                "kubernetes.io/service-account.uid": node_monitoring_sa.metadata.uid,
            },
        ),
        type="kubernetes.io/service-account-token",
        # must ensure the node_monitoring_sa is created else kube-controller-manager will delete
        # the secret as soon as it's created since it references a nonexistent service account
        opts=ResourceOptions(
            parent=node_monitoring_sa,
            provider=provider,
            depends_on=[node_monitoring_sa],
        ),
    )

    # configure role for node-based agents
    node_monitoring_role = rbac.v1.ClusterRole(
        "node-monitoring-role",
        # api_version="rbac.authorization.k8s.io/v1",
        metadata=meta.v1.ObjectMetaArgs(
            name="thunder:node-monitoring",
        ),
        rules=[
            rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=[
                    "services",
                    "events",
                    "endpoints",
                    "pods",
                    "nodes",
                    "namespaces",
                    "componentstatuses",
                ],
                verbs=[
                    "get",
                    "list",
                    "watch",
                ],
            ),
            rbac.v1.PolicyRuleArgs(
                non_resource_urls=[
                    "/version",
                    "/healthz",
                ],
                verbs=["get"],
            ),
            rbac.v1.PolicyRuleArgs(
                non_resource_urls=["/metrics"],
                verbs=["get"],
            ),
            rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=[
                    "nodes/metrics",
                    "nodes/spec",
                    "nodes/proxy",
                    "nodes/stats",
                ],
                verbs=["get"],
            ),
        ],
        opts=ResourceOptions(parent=node_monitoring_sa, provider=provider),
    )

    # configure crb for node-based agents
    rbac.v1.ClusterRoleBinding(
        "node-monitoring-rolebinding",
        # api_version="rbac.authorization.k8s.io/v1",
        metadata=meta.v1.ObjectMetaArgs(
            name="thunder:node-monitoring",
        ),
        subjects=[
            rbac.v1.SubjectArgs(
                kind="ServiceAccount",
                name=node_monitoring_sa.metadata.name,
                namespace="kube-system",
            )
        ],
        role_ref=rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name=node_monitoring_role.metadata.name,
        ),
        opts=ResourceOptions(parent=node_monitoring_role, provider=provider),
    )
