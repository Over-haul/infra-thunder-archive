from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output


@dataclass
class SQSDeduplicationArgs:
    content_based: bool = False
    """For first-in-first-out (FIFO) queues, specifies whether to enable content-based deduplication."""

    scope: Optional[str] = None
    """For high throughput for FIFO queues, specifies whether message deduplication occurs at the message group or queue
    level. Valid values are messageGroup and queue."""


@dataclass
class SQSRedriveArgs:
    deadletter_arn: str
    """The ARN of the dead-letter queue to which SQS moves messages after the value of maxReceiveCount is exceeded."""

    max_receive_count: int
    """The number of times a message is delivered to the source queue before being moved to the dead-letter queue."""


@dataclass
class SQSQueueArgs:
    name: str
    """The name of the queue. A '.fifo' suffix will be added for fifo queues."""

    fifo: bool
    """If set to true, creates a FIFO queue."""

    deduplication: SQSDeduplicationArgs = field(default_factory=SQSDeduplicationArgs)
    """Options for controlling the deduplication of FIFO queues."""

    retention_seconds: int = 345600
    """The number of seconds that Amazon SQS retains a message."""

    fifo_throughput_limit: Optional[str] = None
    """For high throughput for FIFO queues, specifies whether the FIFO queue throughput quota applies to the entire
    queue or per message group. Valid values are perQueue and perMessageGroupId."""

    redrive: Optional[SQSRedriveArgs] = None
    """Options for the dead-letter queue functionality (redrive policy) of this queue."""

    iam_roles: Optional[list[str]] = field(default_factory=list)
    """
    List of ARN with access to this queue, see link
    https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-basic-examples-of-sqs-policies.html#grant-cross-account-permissions-to-role-and-user-name
    """


@dataclass
class SQSConfig:
    queues: list[SQSQueueArgs]


@dataclass
class SQSQueueExport:
    name: str
    """Name of SQS queue"""

    arn: Output[str]
    """ARN of SQS queue"""


@dataclass
class SQSExports:
    queues: list[SQSQueueExport]
