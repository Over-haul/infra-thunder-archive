from enum import Enum


class AttributeType(Enum):
    S = "STRING"
    """the attribute is of type String"""

    N = "NUMBER"
    """the attribute is of type Number"""

    B = "BINARY"
    """the attribute is of type Binary"""


class BillingMode(Enum):
    PAY_PER_REQUEST = "PAY_PER_REQUEST"
    """We recommend using ``PAY_PER_REQUEST`` for unpredictable workloads. ``PAY_PER_REQUEST`` sets the billing mode to
    `On-Demand Mode <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadWriteCapacityMode.html#HowItWorks.OnDemand>`_"""

    PROVISIONED = "PROVISIONED"
    """We recommend using ``PROVISIONED`` for predictable workloads. ``PROVISIONED`` sets the billing mode to
    `Provisioned Mode <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadWriteCapacityMode.html#HowItWorks.ProvisionedThroughput.Manual>`_"""


class ProjectionType(Enum):
    KEYS_ONLY = "KEYS_ONLY"
    """Only the index and primary keys are projected into the index"""

    INCLUDE = "INCLUDE"
    """In addition to the attributes described in KEYS_ONLY, the secondary index will include other non-key attributes that you specify"""

    ALL = "ALL"
    """All of the table attributes are projected into the index"""


class StreamViewType(Enum):
    KEYS_ONLY = "KEYS_ONLY"
    """Only the key attributes of the modified item are written to the stream"""

    NEW_IMAGE = "NEW_IMAGE"
    """The entire item, as it appears after it was modified, is written to the stream"""

    OLD_IMAGE = "OLD_IMAGE"
    """The entire item, as it appeared before it was modified, is written to the stream"""

    NEW_AND_OLD_IMAGES = "NEW_AND_OLD_IMAGES"
    """Both the new and the old item images of the item are written to the stream"""
