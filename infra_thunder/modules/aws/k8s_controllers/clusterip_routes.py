from pulumi import ResourceOptions
from pulumi_aws import ec2

from infra_thunder.lib.route_tables import get_route_tables
from .config import K8sControllerArgs


def create_clusterip_routes(
    cls,
    subnet: ec2.AwaitableGetSubnetResult,
    controller_eni: ec2.NetworkInterface,
    cluster_config: K8sControllerArgs,
):
    """
    Create routes to the ClusterIP range for each controller

    :param cls:
    :param subnet:
    :param controller_eni:
    :param cluster_config:
    :return:
    """

    # get route tables that are in the same az as the eni and add the route
    az = subnet.availability_zone
    for route_table in get_route_tables(vpc_id=cls.vpc.id, availability_zones=[az]).ids:
        ec2.Route(
            f"clusterip-{route_table}",
            route_table_id=route_table,
            destination_cidr_block=cluster_config.service_cidr,
            network_interface_id=controller_eni.id,
            opts=ResourceOptions(parent=controller_eni),
        )
