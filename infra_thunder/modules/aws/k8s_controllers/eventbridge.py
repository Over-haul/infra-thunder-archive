import json
from pulumi import ComponentResource, ResourceOptions
from pulumi_aws import cloudwatch, sqs


from .config import K8sControllerArgs


def create_node_termination_eventbridge_rules(
    cls,
    dependency: ComponentResource,
    node_termination_handler_queue: sqs.Queue,
    cluster_config: K8sControllerArgs,
):
    """
    Create a node termination eventbridge rule.
    """
    rules = [
        (
            f"{cluster_config.name}-asg-termination-rule",
            {"source": ["aws.autoscaling"], "detail-type": ["EC2 Instance-terminate Lifecycle Action"]},
        ),
        (
            f"{cluster_config.name}-spot-termination-rule",
            {"source": ["aws.ec2"], "detail-type": ["EC2 Spot Instance Interruption Warning"]},
        ),
        (
            f"{cluster_config.name}-rebalance-rule",
            {"source": ["aws.ec2"], "detail-type": ["EC2 Instance Rebalance Recommendation"]},
        ),
        (
            f"{cluster_config.name}-instance-state-change-rule",
            {"source": ["aws.ec2"], "detail-type": ["EC2 Instance State-change Notification"]},
        ),
        (
            f"{cluster_config.name}-scheduled-change-rule",
            {
                "source": ["aws.health"],
                "detail-type": ["AWS Health Event"],
                "detail": {"service": ["EC2"], "eventTypeCategory": ["scheduledChange"]},
            },
        ),
    ]
    for name, event_pattern in rules:
        rule = cloudwatch.EventRule(
            name,
            event_pattern=json.dumps(event_pattern),
            opts=ResourceOptions(parent=dependency),
        )
        cloudwatch.EventTarget(
            name,
            rule=rule.name,
            arn=node_termination_handler_queue.arn,
            opts=ResourceOptions(parent=rule),
        )
