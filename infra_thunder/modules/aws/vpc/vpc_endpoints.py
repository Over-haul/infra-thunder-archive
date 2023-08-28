from pulumi import ResourceOptions, get_stack
from pulumi_aws import ec2

from infra_thunder.lib.config import get_sysenv
from infra_thunder.lib.tags import get_tags
from .types import SubnetAndConfig


def setup_vpc_endpoints(
    region: str,
    prefixlist: ec2.ManagedPrefixList,
    vpc: ec2.Vpc,
    subnets: list[SubnetAndConfig],
    route_tables: list[ec2.RouteTable],
):
    allow_ingress = ec2.SecurityGroup(
        f"endpoint-sg",
        ingress=[
            ec2.SecurityGroupIngressArgs(
                description="http to VPC endpoint",
                from_port=80,
                to_port=80,
                protocol="tcp",
                prefix_list_ids=[prefixlist.id],
            ),
            ec2.SecurityGroupIngressArgs(
                description="https to VPC endpoint",
                from_port=443,
                to_port=443,
                protocol="tcp",
                prefix_list_ids=[prefixlist.id],
            ),
        ],
        description=f"Security Group for VPC endpoints {get_stack()} {get_sysenv()}",
        vpc_id=vpc.id,
        tags=get_tags(get_stack(), "security_group", "endpoints"),
        opts=ResourceOptions(parent=vpc),
    )

    s3endpoint = ec2.VpcEndpoint(
        "S3Endpoint",
        service_name=f"com.amazonaws.{region}.s3",
        vpc_id=vpc.id,
        tags=get_tags("VPCEndpoint", "s3"),
        opts=ResourceOptions(parent=vpc),
    )
    ec2endpoint = ec2.VpcEndpoint(
        "EC2Endpoint",
        service_name=f"com.amazonaws.{region}.ec2",
        vpc_id=vpc.id,
        vpc_endpoint_type="Interface",
        security_group_ids=[allow_ingress.id],
        private_dns_enabled=True,
        tags=get_tags("VPCEndpoint", "ec2"),
        opts=ResourceOptions(parent=vpc),
    )

    for subnet, route_table in zip(subnets, route_tables):
        ec2.VpcEndpointRouteTableAssociation(
            f"{subnet.config.purpose}-s3-{subnet.config.availability_zone}",
            route_table_id=route_table.id,
            vpc_endpoint_id=s3endpoint.id,
            opts=ResourceOptions(parent=s3endpoint),
        )
        if subnet.config.purpose == "public":
            ec2.VpcEndpointSubnetAssociation(
                f"{subnet.config.purpose}-ec2-{subnet.config.availability_zone}",
                subnet_id=subnet.subnet.id,
                vpc_endpoint_id=ec2endpoint.id,
                opts=ResourceOptions(parent=ec2endpoint),
            )
