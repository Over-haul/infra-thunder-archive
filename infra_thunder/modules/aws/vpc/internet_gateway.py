from pulumi import ResourceOptions
from pulumi_aws import ec2

from infra_thunder.lib.config import get_sysenv
from infra_thunder.lib.tags import get_tags
from .types import SubnetAndConfig


def setup_igw(vpc: ec2.Vpc, subnets: list[SubnetAndConfig], route_tables: list[ec2.RouteTable]) -> None:
    """
    Create the Internet Gateway and attach it to the public subnets
    :param vpc: VPC to create IGW in
    :param route_tables: Public subnet route tables to attach IGW to
    :return: None
    """
    igw = ec2.InternetGateway(
        "InternetGateway",
        vpc_id=vpc.id,
        tags=get_tags("InternetGateway", get_sysenv()),
        opts=ResourceOptions(parent=vpc),
    )
    for subnet, route_table in zip(subnets, route_tables):
        ec2.Route(
            f"PublicIGWRoute-{subnet.config.availability_zone}",
            route_table_id=route_table.id,
            destination_cidr_block="0.0.0.0/0",
            gateway_id=igw.id,
            opts=ResourceOptions(parent=igw),
        )
