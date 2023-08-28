from dataclasses import dataclass

from pulumi import ResourceOptions
from pulumi_aws import ec2

from infra_thunder.lib.tags import get_tags
from .types import SubnetAndConfig


@dataclass
class NATGateway:
    availability_zone: str
    nat_gateway: ec2.NatGateway


def setup_nat_gateways(
    vpc: ec2.Vpc,
    public_subnets: list[SubnetAndConfig],
    private_subnets: list[SubnetAndConfig],
    private_route_tables: list[ec2.RouteTable],
):
    """
    Create an EIP and NAT gateway in each public subnet, and create a route to the NAT gateway in each private subnet
    to allow instances in the private subnet to access the Internet.

    This function will create NAT gateways for all subnets marked "public"

    """
    # list to hold the created NAT gateways
    nat_gws: list[NATGateway] = []

    # make sure we don't make NATGateways in load balancer public subnets or pod public subnets (if they exist in the config)
    filtered_subnets = filter(lambda x: x.config.purpose == "public", public_subnets)

    for subnet in filtered_subnets:
        eip = ec2.Eip(
            f"{subnet.config.purpose}-nat-{subnet.config.availability_zone}",
            vpc=True,
            tags=get_tags("NAT", "GatewayEIP", subnet.config.availability_zone),
            opts=ResourceOptions(parent=vpc),
        )

        nat_gw = ec2.NatGateway(
            f"{subnet.config.purpose}-nat-{subnet.config.availability_zone}",
            allocation_id=eip.id,
            subnet_id=subnet.subnet.id,
            tags=get_tags("NAT", "Gateway", subnet.config.availability_zone),
            opts=ResourceOptions(parent=eip),
        )
        nat_gws.append(NATGateway(availability_zone=subnet.config.availability_zone, nat_gateway=nat_gw))

    _setup_nat_routes(nat_gws, private_subnets, private_route_tables)


def _setup_nat_routes(
    nat_gws: list[NATGateway],
    private_subnets: list[SubnetAndConfig],
    private_route_tables: list[ec2.RouteTable],
):
    # lookup map for az -> nat gateway to allow multiple subnets
    nat_az_map = {nat_gw.availability_zone: nat_gw.nat_gateway for nat_gw in nat_gws}

    # create a route in each private route table to the NAT gateway in the appropriate availability zone
    for private_subnet, private_route_table in zip(private_subnets, private_route_tables):
        ec2.Route(
            f"{private_subnet.config.purpose}-nat-{private_subnet.config.availability_zone}",
            destination_cidr_block="0.0.0.0/0",
            route_table_id=private_route_table.id,
            nat_gateway_id=nat_az_map[private_subnet.config.availability_zone].id,
            opts=ResourceOptions(parent=private_route_table),
        )
