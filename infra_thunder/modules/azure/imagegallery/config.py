from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output


@dataclass
class ImageGalleryArgs:
    name: str
    """The name of the Shared Image Gallery."""

    description: Optional[str]
    """The description of this Shared Image Gallery resource."""


@dataclass
class ImageGalleryConfig:
    extra_galleries: list[ImageGalleryArgs] = field(default_factory=list)


@dataclass
class ImageGalleryExport:
    name: Output[str]
