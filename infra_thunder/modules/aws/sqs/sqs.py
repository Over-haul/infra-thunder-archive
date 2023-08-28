import json
from typing import Optional

from pulumi import ResourceOptions
from pulumi_aws import sqs

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.tags import get_tags
from .config import (
    SQSConfig,
    SQSDeduplicationArgs,
    SQSQueueExport,
    SQSRedriveArgs,
    SQSExports,
)


class SQS(AWSModule):
    def build(self, config: SQSConfig) -> SQSExports:
        queues = [
            self._create_queue(
                name=queue.name,
                fifo=queue.fifo,
                deduplication=queue.deduplication,
                retention_seconds=queue.retention_seconds,
                fifo_throughput_limit=queue.fifo_throughput_limit,
                redrive=queue.redrive,
                iam_roles=queue.iam_roles,
            )
            for queue in config.queues
        ]

        return SQSExports(
            queues=queues,
        )

    def _create_queue(
        self,
        name: str,
        fifo: bool,
        deduplication: SQSDeduplicationArgs,
        retention_seconds: int,
        fifo_throughput_limit: Optional[str],
        redrive: Optional[SQSRedriveArgs],
        iam_roles: Optional[list[str]] = None,
    ) -> SQSQueueExport:
        queue = sqs.Queue(
            name,
            name=f"{name}.fifo" if fifo else name,
            fifo_queue=fifo,
            content_based_deduplication=deduplication.content_based,
            deduplication_scope=deduplication.scope,
            message_retention_seconds=retention_seconds,
            fifo_throughput_limit=fifo_throughput_limit,
            redrive_policy=json.dumps(
                {
                    "deadLetterTargetArn": redrive.deadletter_arn,
                    "maxReceiveCount": redrive.max_receive_count,
                }
            )
            if redrive
            else None,
            tags=get_tags(service="sqs", role="queue", group=name),
            opts=ResourceOptions(parent=self),
        )

        if iam_roles:
            sqs.QueuePolicy(
                name,
                queue_url=queue.id,
                policy=queue.arn.apply(
                    lambda arn: json.dumps(
                        {
                            "Version": "2012-10-17",
                            "Id": "CrossAccountSQSPolicy",
                            "Statement": [
                                {
                                    "Sid": "SQSPolicy",
                                    "Effect": "Allow",
                                    "Principal": {"AWS": iam_roles},
                                    "Action": ["sqs:*"],
                                    "Resource": arn,
                                }
                            ],
                        }
                    )
                ),
            )

        return SQSQueueExport(
            name=name,
            arn=queue.arn,
        )
