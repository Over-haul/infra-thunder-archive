from pulumi import ComponentResource, ResourceOptions
from pulumi_aws import sqs


from infra_thunder.lib.tags import get_tags, get_stack
from .config import K8sControllerConfig


def create_node_termination_sqs_queue(
    cls,
    dependency: ComponentResource,
    cluster_config: K8sControllerConfig,
):
    queue = sqs.Queue(
        f"{cluster_config.name}-node-termination",
        name=f"{cluster_config.name}-node-termination",
        fifo_queue=False,
        message_retention_seconds=300,
        tags=get_tags(service=get_stack(), role="node-termination"),
        opts=ResourceOptions(parent=dependency),
    )
    sqs.QueuePolicy(
        f"{cluster_config.name}-node-termination-sqs-policy",
        queue_url=queue.id,
        policy={
            "Version": "2012-10-17",
            "Id": "NodeTerminationQueuePolicy",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": ["events.amazonaws.com", "sqs.amazonaws.com"]},
                    "Action": "sqs:SendMessage",
                    "Resource": [
                        queue.arn,
                    ],
                }
            ],
        },
        opts=ResourceOptions(parent=queue),
    )
    return queue
