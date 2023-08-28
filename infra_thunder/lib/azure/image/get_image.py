from functools import lru_cache
from typing import Optional

from pulumi_azure_native import compute
from pulumi_azure_native.compute import GetGalleryImageResult

from infra_thunder.lib.config import thunder_env, get_sysenv


def _get_config(gallery_name: Optional[str] = None, resource_group_name: Optional[str] = None):
    """
    Image gallery names and resource groups can be overridden by setting thunder_env variables, or by calling
    this function directly with the overrides.

    Image gallery resource group is sourced from:
    - thunder_env `imagegallery_sysenv`
    - explicit arguments

    Image gallery name is sourced from:
    - thunder_env `imagegallery_name`
    - explicit argument
    - name of the image gallery resource group

    :param gallery_name:
    :param resource_group_name:
    :return:
    """

    sysenv = get_sysenv()

    gallery_resourcegroup_env = thunder_env.get("imagegallery_sysenv")
    # try argument, env, or fall back to sysenv name of the current sysenv
    gallery_resourcegroup_ = resource_group_name or gallery_resourcegroup_env or sysenv

    gallery_name_env = thunder_env.get("imagegallery_name")
    # try argument, env, or fall back to sysenv name
    gallery_name_ = gallery_name or gallery_name_env or gallery_resourcegroup_.replace("-", "_")

    return gallery_resourcegroup_, gallery_name_


def get_gallery(gallery_name: Optional[str] = None, resource_group_name: Optional[str] = None):
    resource_group_name_, gallery_name_ = _get_config(gallery_name, resource_group_name)

    return compute.get_gallery(
        resource_group_name=resource_group_name_,
        gallery_name=gallery_name_,
    )


def get_image_version(
    gallery_image_name: str,
    gallery_image_version_name: str,
    gallery_name: Optional[str] = None,
    resource_group_name: Optional[str] = None,
):
    resource_group_name_, gallery_name_ = _get_config(gallery_name, resource_group_name)

    return compute.get_gallery_image_version(
        gallery_image_name=gallery_image_name,
        gallery_image_version_name=gallery_image_version_name,
        resource_group_name=resource_group_name_,
        gallery_name=gallery_name_,
    )


@lru_cache
def get_image(
    gallery_image_name: str,
    gallery_name: Optional[str] = None,
    resource_group_name: Optional[str] = None,
) -> GetGalleryImageResult:
    resource_group_name_, gallery_name_ = _get_config(gallery_name, resource_group_name)

    return compute.get_gallery_image(
        gallery_image_name=gallery_image_name,
        resource_group_name=resource_group_name_,
        gallery_name=gallery_name_,
    )
