from dataclasses import dataclass
from typing import Optional

from pulumi import Output


@dataclass
class SeedConfig:
    seed_override: Optional[str]
    """Override the seed uuid"""

    byte_length: Optional[int] = 6
    """The number of random bytes to produce. These bytes will then be base64 encoded."""


@dataclass
class SeedExports:
    seed: Output[str]
