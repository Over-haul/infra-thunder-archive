from dataclasses import dataclass
from typing import Optional


@dataclass
class Cluster:
    name: str
    """Name for the elasticsearch cluster (Example: logs)"""

    data_volume_size: Optional[int]
    """Size of the EBS volume where elasticsearch data is stored"""

    data_volume_type: Optional[str]
    """Type of EBS volume where elasticsearch data is stored (Examples: gp2, io2, st1)"""

    volume_size: int = 20
    """Size of the EBS volume for root partition (Operating System)"""

    volume_type: str = "gp2"
    """Type of EBS volume for root partition (Examples: gp2, io2, st1)"""

    instance_type: str = "t3.medium"
    """EC2 Instance Type for elasticsearch members"""

    count: int = 3
    """Amount of members in the elasticsearch cluster"""


@dataclass
class ElasticSearchArgs:
    s3_backup_bucket: str
    """S3 Bucket where elasticsearch backups are stored into"""

    clusters: list[Cluster]
    """List of elasticsearch clusters to create"""
