from dataclasses import dataclass


@dataclass
class Cluster:
    name: str
    """Name for the rabbitmq cluster (Example: logs)"""

    volume_size: int = 20
    """Size of the EBS volume for root partition (Operating System)"""

    volume_type: str = "gp2"
    """Type of EBS volume for root partition (Examples: gp2, io2, st1)"""

    instance_type: str = "t3.medium"
    """EC2 Instance Type for rabbitmq members"""

    count: int = 3
    """Amount of members in the rabbitmq cluster"""


@dataclass
class RabbitMQArgs:
    clusters: list[Cluster]
    """List of rabbitmq clusters to create"""
