from typing import Optional

from pulumi import ResourceOptions
from pulumi_azure_native import compute

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.config import get_sysenv
from infra_thunder.lib.tags import get_tags
from .config import ImageGalleryConfig, ImageGalleryExport


class ImageGallery(AzureModule):
    def build(self, config: ImageGalleryConfig) -> list[ImageGalleryExport]:
        # gallery name may not contain "-"
        # https://docs.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules#microsoftcompute
        default_gallery = self._create_image_gallery(
            name=get_sysenv().replace("-", "_"),
            description="Default Image Gallery",
        )

        extra_galleries = [
            self._create_image_gallery(
                name=gallery.name,
                description=gallery.description,
            )
            for gallery in config.extra_galleries
        ]

        return [default_gallery, *extra_galleries]

    def _create_image_gallery(self, name: str, description: Optional[str]) -> ImageGalleryExport:
        gallery = compute.gallery.Gallery(
            name,
            gallery_name=name,
            description=description,
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="imagegallery", role="imagegallery", group=name),
            opts=ResourceOptions(parent=self),
        )

        return ImageGalleryExport(
            name=gallery.name,
        )
