from dataclasses import dataclass

from pulumi import Output


@dataclass
class KinesisStreamArgs:
    name: str
    """A name to identify the stream"""

    shards: int
    """The number of shards that the stream will use."""

    retention_hours: int = 24
    """Length of time data records are accessible after they are added to the stream."""


@dataclass
class KinesisConfig:
    streams: list[KinesisStreamArgs]


@dataclass
class KinesisStreamExport:
    name: Output[str]
    """Stream name"""

    arn: Output[str]
    """Stream ARN"""


@dataclass
class KinesisExports:
    streams: list[KinesisStreamExport]
    """List of Kinesis Streams created by this module"""
