from dataclasses import dataclass, field
from typing import Optional

from pulumi import Output


@dataclass
class DatadogConfig:
    api_key: Optional[str] = None
    """API Key if you want to use a different one than the one stored in SSM."""

    app_key: Optional[str] = None
    """App Key if you want to use a different one than the one stored in SSM."""

    datadog_site: Optional[str] = None
    """
    The site of the Datadog intake to send Agent data to.
    Set to 'datadoghq.com' to send data to the US1 site.
    Set to 'datadoghq.eu' to send data to the EU site.
    Set to 'us3.datadoghq.com' to send data to the US3 site.
    Set to 'us5.datadoghq.com' to send data to the US5 site.
    Set to 'ap1.datadoghq.com' to send data to the AP1 site.
    Set to 'ddog-gov.com' to send data to the US1-FED site.
    For more visit: https://docs.datadoghq.com/getting_started/site/#access-the-datadog-site
    """

    extra_regions: Optional[list[str]] = field(default_factory=list)
    """Extra aws regions to deploy metrics stream to besides current region"""

    forwarder_version: Optional[str] = "3.73.0"
    """
    Version of the forwarder to use.
    See https://github.com/DataDog/datadog-serverless-functions
    """


@dataclass
class DatadogExports:
    external_id: Output[str]
    """
    AWS External ID.
    NOTE This provider will not be able to detect changes made to the ``external_id`` field from outside Terraform
    """

    id: Output[str]
    """The provider-assigned unique ID for this managed resource."""
