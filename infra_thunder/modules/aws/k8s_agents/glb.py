from pulumi import ResourceOptions, Output, ComponentResource
from pulumi_aws import ec2, lb

from infra_thunder.lib.config import get_stack
from infra_thunder.lib.route_tables import get_route_tables
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_tags
from .generate_lb_name import generate_lb_name


def create_glb(
    cls, dependency: ComponentResource, cluster_name: str
) -> (lb.TargetGroup, lb.LoadBalancer, ec2.VpcEndpoint):
    short_resource_name = generate_lb_name(cluster_name)

    tg = lb.TargetGroup(
        f"{short_resource_name}-glb-tg",
        port=6081,
        protocol="GENEVE",
        vpc_id=cls.vpc.id,
        health_check=lb.TargetGroupHealthCheckArgs(
            port="6081",
            protocol="TCP",
        ),
        deregistration_delay=30,
        tags=get_tags(get_stack(), "glb", cluster_name),
        opts=ResourceOptions(parent=dependency),
    )

    # glb_sg = generate_security_group(
    #     name=f"{short_resource_name}-glb",
    #     ingress_rules=[SecurityGroupIngressRule(
    #         description="Allow all traffic inbound from supernet",
    #         from_port=0,
    #         to_port=0,
    #         protocol="-1",
    #         allow_vpc_supernet=True,
    #     )],
    #     opts=ResourceOptions(parent=dependency)
    # )

    glb = lb.LoadBalancer(
        f"{short_resource_name}-glb",
        internal=False,
        load_balancer_type="gateway",
        # security_groups=[glb_sg] + get_default_security_groups(cls.vpc.id).ids,
        subnets=[subnet.id for subnet in get_subnets_attributes(public=False, purpose="private", vpc_id=cls.vpc.id)],
        tags=get_tags(get_stack(), "glb", cluster_name),
        opts=ResourceOptions(parent=tg),
    )

    endpoint_service = ec2.VpcEndpointService(
        f"{short_resource_name}-glb-endpointsvc",
        acceptance_required=False,
        gateway_load_balancer_arns=[glb.arn],
        tags=get_tags(get_stack(), "glb-endpointsvc", cluster_name),
        opts=ResourceOptions(parent=glb),
    )

    endpoint = ec2.VpcEndpoint(
        f"{short_resource_name}-glb-endpoint",
        vpc_endpoint_type=endpoint_service.service_type,
        service_name=endpoint_service.service_name,
        vpc_id=cls.vpc.id,
        subnet_ids=[
            get_subnets_attributes(public=False, purpose="private", vpc_id=cls.vpc.id)[0].id
        ],  # TODO: can only have a single subnet per VPCEndpoint??
        opts=ResourceOptions(parent=endpoint_service),
    )

    lb.Listener(
        f"{short_resource_name}-GENEVE",
        load_balancer_arn=glb.arn,
        default_actions=[
            lb.ListenerDefaultActionArgs(
                type="forward",
                target_group_arn=tg.arn,
            )
        ],
        opts=ResourceOptions(parent=glb),
    )

    return tg, glb, endpoint


def create_glb_routes(cls, controller_config: Output, endpoint: ec2.VpcEndpoint):
    service_cidr = controller_config["service_cidr"]
    for route_table in get_route_tables(vpc_id=cls.vpc.id).ids:
        ec2.Route(
            f"glb-{route_table}",
            route_table_id=route_table,
            destination_cidr_block=service_cidr,
            vpc_endpoint_id=endpoint.id,
            opts=ResourceOptions(parent=endpoint),
        )
