from pulumi import ResourceOptions
from pulumi_aws import kinesis

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.tags import get_tags
from .config import KinesisConfig, KinesisStreamExport, KinesisExports


class Kinesis(AWSModule):
    def build(self, config: KinesisConfig) -> KinesisExports:
        streams = [self._create_stream(stream.name, stream.shards, stream.retention_hours) for stream in config.streams]

        return KinesisExports(streams=streams)

    def _create_stream(self, name: str, shards: int, retention_hours: int) -> KinesisStreamExport:
        stream = kinesis.Stream(
            name,
            name=name,
            shard_count=shards,
            retention_period=retention_hours,
            tags=get_tags(service="kinesis", role="stream", group=name),
            opts=ResourceOptions(parent=self),
        )

        return KinesisStreamExport(
            name=stream.name,
            arn=stream.arn,
        )
