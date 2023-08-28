import json
from pulumi import ResourceOptions
from pulumi_aws import iam, sqs
from pulumi_kubernetes import provider as kubernetes_provider

from infra_thunder.lib.config import tag_prefix
from infra_thunder.lib.kubernetes.common.annotations.monitoring_annotations import (
    get_datadog_annotations,
)
from infra_thunder.lib.kubernetes.constants import NODEGROUP_TAG_KEY
from infra_thunder.lib.kubernetes.helm import HelmChartStack
from infra_thunder.lib.kubernetes.helm.config import HelmChart
from ..config import K8sControllerArgs


def _remove_metrics_service(obj, opts):
    """
    This transformation function mutates the Helm chart for AWS Node termination handler to remove the metrics service
    """
    if obj["kind"] == "Service" and obj["metadata"]["name"] == "aws-node-termination-handler":
        obj.clear()
        obj.update({"apiVersion": "v1", "kind": "List"})


def configure_aws_node_termination_handler(
    provider: kubernetes_provider.Provider,
    node_termination_handler_role: iam.Role,
    node_termination_handler_queue: sqs.Queue,
    cluster_config: K8sControllerArgs,
):
    """
    Configure the AWS Node Termination Handler
    :return:
    """
    slack_webhook_template = json.dumps(
        {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "AWS Node Termination Handler: Received instance interruption event",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": "*Start Time:*\n{{ .StartTime }}"},
                        {"type": "mrkdwn", "text": "*Kind:*\n{{ .Kind }}"},
                        {"type": "mrkdwn", "text": "*Event ID:*\n{{ .EventID }}"},
                        {"type": "mrkdwn", "text": "*Description:*\n{{ .Description }}"},
                    ],
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": "*Node Labels:*\n {{ range $key, $value := .NodeLabels }}• *{{ $key }}*: {{ $value }}\n{{ end }}",
                            "verbatim": True,
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*Pods on Node:*\n {{ range $pod := .Pods }}• `{{ $pod }}`\n{{ end }}",
                            "verbatim": True,
                        },
                    ],
                },
            ]
        }
    )
    prometheus_port = "9092"
    HelmChartStack(
        "aws-node-termination-handler",
        namespace=cluster_config.name,
        chart=HelmChart(
            chart="aws-node-termination-handler",
            repo="https://aws.github.io/eks-charts",
            namespace="kube-system",
            version="0.18.5",
            transformations=[_remove_metrics_service],
            values={
                "enableSqsTerminationDraining": True,
                "enableScheduledEventDraining": True,
                "enableRebalanceMonitoring": True,
                "enableRebalanceDraining": True,
                "enablePrometheusServer": True,
                "prometheusServerPort": prometheus_port,
                "jsonLogging": True,
                "podAnnotations": {
                    "iam.amazonaws.com/role": node_termination_handler_role.arn,
                    **get_datadog_annotations(
                        "aws-node-termination-handler",
                        "openmetrics",
                        {
                            "openmetrics_endpoint": f"http://%%host%%:{prometheus_port}/metrics",
                            "namespace": "kubernetes.aws-node-termination-handler",
                            "metrics": ["actions_node", "events_error"],
                        },
                    ),
                },
                "queueURL": node_termination_handler_queue.id,
                "managedAsgTag": f"{tag_prefix}{NODEGROUP_TAG_KEY}",
                "webhookURL": cluster_config.node_termination_webhook_url,
                "webhookTemplate": cluster_config.node_termination_webhook_template or slack_webhook_template,
                "useProviderId": True,
                "tolerations": [
                    {
                        "operator": "Exists",
                        "effect": "NoSchedule",
                    }
                ],
                "nodeSelector": {
                    "node-role.kubernetes.io/control-plane": "",
                },
                "resources": {
                    "requests": {
                        "cpu": "100m",
                        "memory": "128Mi",
                    },
                    "limits": {"cpu": "500m", "memory": "256Mi"},
                },
            },
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )
