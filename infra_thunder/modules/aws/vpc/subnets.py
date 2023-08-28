from pulumi import ResourceOptions
from pulumi_aws import ec2

from infra_thunder.lib.tags import get_tags
from .config import VPCSubnetConfig
from .types import SubnetAndConfig


def setup_subnets(
    region: str, vpc: ec2.Vpc, subnet_configs: list[VPCSubnetConfig], is_public=False
) -> (list[SubnetAndConfig], list[ec2.RouteTable]):
    """
    Create subnets and their associated route tables
    :param region: AWS region to create these resources in
    :param vpc: VPC object to create subnets in
    :param subnet_configs: List of VPCSubnetConfig objects to materialize
    :param is_public: Will instances in this subnet receive public IP addresses on boot?
    :return: List of materialized subnets
    """
    # Create the subnets
    subnets: list[SubnetAndConfig] = list(_generate_subnets(vpc, subnet_configs, assign_public_ip=is_public))

    # Create route tables for each availability zone, and associate them with each subnet
    route_tables = list(_generate_route_tables(vpc, subnets))
    for i, subnet in enumerate(subnets):
        ec2.RouteTableAssociation(
            f"{subnet.config.purpose}-{subnet.config.availability_zone}",
            subnet_id=subnet.subnet.id,
            route_table_id=route_tables[i].id,
            opts=ResourceOptions(parent=subnet.subnet),
        )
    return subnets, route_tables


def _generate_subnets(
    vpc: ec2.Vpc, subnet_configs: list[VPCSubnetConfig], assign_public_ip=False
) -> list[SubnetAndConfig]:
    """
    Generate subnet definitions
    :param vpc: VPC object to create subnets in
    :param subnet_configs: Subnet definition
    :param assign_public_ip: Assign public IP to instances in this subnet on launch
    :return: Subnet definition generator
    """
    for config in subnet_configs:
        yield SubnetAndConfig(
            config=config,
            subnet=ec2.Subnet(
                f"{config.purpose}-{config.availability_zone}",
                vpc_id=vpc.id,
                availability_zone=config.availability_zone,
                cidr_block=config.cidr_block,
                map_public_ip_on_launch=assign_public_ip,
                tags=get_tags("subnet", config.purpose, config.availability_zone),
                opts=ResourceOptions(parent=vpc),
            ),
        )


def _generate_route_tables(vpc: ec2.Vpc, subnets: list[SubnetAndConfig]) -> list[ec2.RouteTable]:
    """
    Generate route tables from a list of subnets and subnet configurations
    :param vpc: VPC object to create route tables for
    :param subnets: List of SubnetAndConfig objects to create route tables for
    :return: List of route tables
    """
    for subnet in subnets:
        yield _generate_route_table(vpc, subnet.subnet, subnet.config)


def _generate_route_table(vpc: ec2.Vpc, subnet: ec2.Subnet, subnet_config: VPCSubnetConfig) -> ec2.RouteTable:
    """
    Generate an individual route table
    :param vpc: VPC object to create route tables for
    :param subnet: ec2.Subnet object to create route table for
    :param subnet_config: VPCSubnetConfig object matching with the ec2.Subnet
    :return: Route table
    """
    return ec2.RouteTable(
        f"{subnet_config.purpose}-{subnet_config.availability_zone}",
        vpc_id=vpc.id,
        tags=get_tags("routetable", subnet_config.purpose, subnet_config.availability_zone),
        opts=ResourceOptions(parent=subnet),
    )
