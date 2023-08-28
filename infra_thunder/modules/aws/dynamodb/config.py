from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output

from .types import AttributeType, BillingMode, ProjectionType, StreamViewType


@dataclass
class Attribute:
    name: str
    """
    A name for the attribute
    Length Constraints: Minimum length of 1. Maximum length of 255
    """

    type: AttributeType
    """
    The data type for the attribute, where:
        ``S`` - the attribute is of type String
        ``N`` - the attribute is of type Number
        ``B`` - the attribute is of type Binary
    """


@dataclass
class TableGlobalSecondaryIndex:
    hash_key: str
    """The name of the hash key in the index; must be defined as an attribute in the resource."""

    name: str
    """
    The name of the global secondary index. The name must be unique among all other indexes on this table.
    Length Constraints: Minimum length of 3. Maximum length of 255
    Pattern: ``[a-zA-Z0-9_.-]+``
    """

    projection_type: ProjectionType
    """
    The set of attributes that are projected into the index:
        KEYS_ONLY - Only the index and primary keys are projected into the index.
        INCLUDE - In addition to the attributes described in KEYS_ONLY, the secondary index will include other non-key attributes that you specify.
        ALL - All of the table attributes are projected into the index.
    """

    range_key: str
    """The name of the range key; must be defined"""

    read_capacity: Optional[int]
    """The number of read units for this index. Must be set if ``billing_mode`` is set to ``PROVISIONED``"""

    write_capacity: Optional[int]
    """The number of write units for this index. Must be set if ``billing_mode`` is set to ``PROVISIONED``"""

    non_key_attributes: Optional[list[str]] = field(default_factory=list)
    """
    Only required with ``INCLUDE`` as a projection type; a list of attributes to project into the index.
    These do not need to be defined as attributes on the table.
    """


@dataclass
class TableLocalSecondaryIndex:
    name: str
    """
    The name of the global secondary index. The name must be unique among all other indexes on this table.
    Length Constraints: Minimum length of 3. Maximum length of 255
    Pattern: ``[a-zA-Z0-9_.-]+``
    """

    projection_type: ProjectionType
    """
    The set of attributes that are projected into the index:
        KEYS_ONLY - Only the index and primary keys are projected into the index.
        INCLUDE - In addition to the attributes described in KEYS_ONLY, the secondary index will include other non-key attributes that you specify.
        ALL - All of the table attributes are projected into the index.
    """

    range_key: str
    """The name of the range key; must be defined"""

    non_key_attributes: Optional[list[str]] = field(default_factory=list)
    """
    Only required with ``INCLUDE`` as a projection type; a list of attributes to project into the index.
    These do not need to be defined as attributes on the table.
    """


@dataclass
class ServerSideEncryption:
    kms_key_arn: Optional[str]
    """
    The ARN of the CMK that should be used for the AWS KMS encryption.
    This attribute should only be specified if the key is different from the default DynamoDB CMK, ``alias/aws/dynamodb``
    """

    enabled: bool = True
    """Whether or not to enable encryption at rest using an AWS managed KMS customer master key (CMK)"""


@dataclass
class TableReplica:
    region_name: str
    """Region names for creating replicas for a global DynamoDB table"""

    kms_key_arn: Optional[str]
    """
    The ARN of the CMK that should be used for the AWS KMS encryption.
    This attribute should only be specified if the key is different from the default DynamoDB CMK, ``alias/aws/dynamodb``
    """


@dataclass
class TableTtl:
    attribute_name: Optional[str]
    """The name of the table attribute to store the TTL timestamp in"""

    kms_key_arn: Optional[str]
    """
    The ARN of the CMK that should be used for the AWS KMS encryption.
    This attribute should only be specified if the key is different from the default DynamoDB CMK, ``alias/aws/dynamodb``
    """

    enabled: bool = True
    """Indicates whether ttl is enabled"""


@dataclass
class Table:
    hash_key: str
    """The attribute to use as the hash (partition) key. Must also be defined as an attribute"""

    name: str
    """Table name"""

    range_key: Optional[str]
    """The attribute to use as the range (sort) key. Must also be defined as an attribute"""

    read_capacity: Optional[int]
    """The number of read units for this table. If the billing_mode is PROVISIONED, this field should be greater than 0"""

    server_side_encryption: Optional[ServerSideEncryption]
    """Encryption at rest options. AWS DynamoDB tables are automatically encrypted at rest with an AWS owned Customer Master Key if this argument isn't specified"""

    stream_view_type: Optional[StreamViewType]
    """
    When an item in the table is modified, StreamViewType determines what information is written to the table's stream.
        KEYS_ONLY - Only the key attributes of the modified item are written to the stream.
        NEW_IMAGE - The entire item, as it appears after it was modified, is written to the stream.
        OLD_IMAGE - The entire item, as it appeared before it was modified, is written to the stream.
        NEW_AND_OLD_IMAGES - Both the new and the old item images of the item are written to the stream.
    """

    ttl: Optional[TableTtl]
    """Defines Time To Live"""

    write_capacity: Optional[int]
    """The number of write units for this table. If the billing_mode is PROVISIONED, this field should be greater than 0"""

    attributes: Optional[list[Attribute]] = field(default_factory=list)
    """List of nested attribute definitions. Only required for ``hash_key`` and ``range_key`` attributes. Each attribute has two properties"""

    billing_mode: BillingMode = BillingMode.PAY_PER_REQUEST
    """Controls how you are charged for read and write throughput and how you manage capacity. This setting can be changed later"""

    global_secondary_indexes: Optional[list[TableGlobalSecondaryIndex]] = field(default_factory=list)
    """Describe a GSI for the table; subject to the normal limits on the number of GSIs, projected attributes, etc."""

    local_secondary_indexes: Optional[list[TableLocalSecondaryIndex]] = field(default_factory=list)
    """Describe an LSI on the table; these can only be allocated at creation so you cannot change this definition after you have created the resource"""

    point_in_time_recovery_enabled: bool = False
    """Whether to enable point-in-time recovery"""

    replicas: Optional[list[TableReplica]] = field(default_factory=list)
    """List of region and ARN of CMK that should be used for the AWS KMS encryption"""

    stream_enabled: bool = False
    """Indicates whether Streams are to be enabled (true) or disabled (false)"""


@dataclass
class Tables:
    tables: list[Table]
    """List of Table specifications."""


@dataclass
class DynamoDBExports:
    id: Output[str]
    """The provider-assigned unique ID for this managed resource"""

    arn: Output[str]
    """The arn of the table"""

    stream_arn: Optional[Output[str]] = None
    """
    The ARN of the Table Stream.
    Only available when ``stream_enabled = true``
    """

    stream_label: Optional[Output[str]] = None
    """
    A timestamp, in ISO 8601 format, for this stream. Note that this timestamp is not a unique identifier for the stream on its own.
    However, the combination of AWS customer ID, table name and this field is guaranteed to be unique.
    It can be used for creating CloudWatch Alarms.
    ``Only available when stream_enabled = true``
    """
