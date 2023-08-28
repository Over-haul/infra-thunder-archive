from pulumi_aws import dynamodb

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import get_stack
from infra_thunder.lib.tags import get_tags
from .config import Table, Tables, DynamoDBExports


class DynamoDB(AWSModule):
    def build(self, config: Tables) -> list[DynamoDBExports]:
        return [self._create_table(table) for table in config.tables]

    def _create_table(self, args: Table) -> DynamoDBExports:
        table = dynamodb.Table(
            args.name,
            attributes=[
                dynamodb.TableAttributeArgs(
                    name=attr.name,
                    type=attr.type.name,
                )
                for attr in args.attributes
            ],
            hash_key=args.hash_key,
            billing_mode=args.billing_mode.value,
            global_secondary_indexes=[
                dynamodb.TableGlobalSecondaryIndexArgs(
                    hash_key=index.hash_key,
                    name=index.name,
                    non_key_attributes=index.non_key_attributes,
                    projection_type=index.projection_type.value,
                    range_key=index.range_key,
                    read_capacity=index.read_capacity,
                    write_capacity=index.write_capacity,
                )
                for index in args.global_secondary_indexes
            ],
            local_secondary_indexes=[
                dynamodb.TableLocalSecondaryIndexArgs(
                    name=index.name,
                    projection_type=index.projection_type.value,
                    range_key=index.range_key,
                    non_key_attributes=index.non_key_attributes,
                )
                for index in args.local_secondary_indexes
            ],
            point_in_time_recovery=dynamodb.TablePointInTimeRecoveryArgs(enabled=args.point_in_time_recovery_enabled),
            range_key=args.range_key,
            read_capacity=args.read_capacity,
            replicas=[
                dynamodb.TableReplicaArgs(region_name=replica.region_name, kms_key_arn=replica.kms_key_arn)
                for replica in args.replicas
            ],
            server_side_encryption=dynamodb.TableServerSideEncryptionArgs(
                enabled=args.server_side_encryption.enabled,
                kms_key_arn=args.server_side_encryption.kms_key_arn,
            )
            if args.server_side_encryption
            else None,
            stream_enabled=args.stream_enabled,
            stream_view_type=args.stream_view_type.value if args.stream_view_type else None,
            ttl=dynamodb.TableTtlArgs(
                attribute_name=args.ttl.attribute_name,
                enabled=args.ttl.enabled,
                kms_key_arn=args.ttl.kms_key_arn,
            )
            if args.ttl
            else None,
            write_capacity=args.write_capacity,
            tags=get_tags(get_stack(), "table", args.name),
        )

        return DynamoDBExports(
            id=table.id,
            arn=table.arn,
            stream_arn=table.stream_arn,
            stream_label=table.stream_label,
        )
