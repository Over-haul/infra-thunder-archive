from pulumi import Output, ResourceOptions
from pulumi_aws import ec2, elasticache, ssm
from pulumi_random import RandomPassword

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import get_stack, get_sysenv
from infra_thunder.lib.security_groups import (
    SecurityGroupIngressRule,
    generate_security_group,
    get_default_security_groups,
)
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_tags
from infra_thunder.lib.vpc import get_vpc
from .config import ReplicationGroup, ReplicationGroups, ElasticacheExports


class Elasticache(AWSModule):
    def build(self, config: ReplicationGroups) -> list[ElasticacheExports]:
        vpc = get_vpc()
        subnets = get_subnets_attributes(public=False, purpose="private", vpc_id=vpc.id)
        subnet_group = elasticache.SubnetGroup(
            get_stack(),
            description=f"{get_stack()} subnet group for {get_sysenv()}",
            subnet_ids=[subnet.id for subnet in subnets],
        )
        return [self._create_replication_group(rg, vpc, subnet_group) for rg in config.replication_groups]

    def _create_replication_group(
        self,
        args: ReplicationGroup,
        vpc: ec2.AwaitableGetVpcResult,
        subnet_group: elasticache.SubnetGroup,
    ) -> ElasticacheExports:
        replication_group_name = f"{get_stack()}-{args.name}"

        # See:
        # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticache-parameter-group.html
        parameter_group = elasticache.ParameterGroup(
            replication_group_name,
            family=f"{args.engine}{args.engine_version}",
            parameters=[
                elasticache.ParameterGroupParameterArgs(name=param.name, value=param.value) for param in args.rg_params
            ],
            opts=ResourceOptions(parent=subnet_group),
        )

        ingress_rules = [
            SecurityGroupIngressRule(
                description="redis",
                from_port=6379,
                to_port=6379,
                protocol="tcp",
                allow_vpc_supernet=True,
                allow_peered_supernets=True,
            ),
            SecurityGroupIngressRule(
                description="any port from self",
                from_port=0,
                to_port=0,
                protocol="-1",
                self=True,
            ),
        ]

        security_group = generate_security_group(
            ingress_rules=ingress_rules,
            vpc_id=vpc.id,
            name=replication_group_name,
            opts=ResourceOptions(parent=self),
        )

        rg_password = None
        if args.transit_encryption_enabled:
            rg_password = RandomPassword(
                replication_group_name,
                length=32,
                special=False,
                opts=ResourceOptions(parent=parameter_group),
            )
            ssm.Parameter(
                f"{replication_group_name}-password",
                name=f"/Infrastructure/{get_sysenv()}/{get_stack()}/{args.name}/MASTER_PASSWORD",
                type="SecureString",
                value=rg_password.result,
                opts=ResourceOptions(parent=rg_password),
            )

        replication_group = elasticache.ReplicationGroup(
            resource_name=replication_group_name,
            at_rest_encryption_enabled=True,
            auth_token=rg_password.result if args.transit_encryption_enabled else None,
            auto_minor_version_upgrade=True,
            automatic_failover_enabled=args.automatic_failover,
            availability_zones=args.availability_zones,
            engine_version=args.engine_version,
            engine=args.engine,
            maintenance_window="sat:09:00-sat:10:00",
            node_type=args.instance_type,
            number_cache_clusters=args.num_node_groups,
            parameter_group_name=parameter_group.name,
            port=6379,
            replication_group_description=f"{replication_group_name} replication group",
            security_group_ids=[security_group.id] + get_default_security_groups(vpc_id=vpc.id).ids,
            subnet_group_name=subnet_group,
            transit_encryption_enabled=args.transit_encryption_enabled,
            tags=get_tags(get_stack(), "cluster", args.name),
            opts=ResourceOptions(parent=parameter_group),
        )

        ssm.Parameter(
            f"{replication_group_name}-connectionuri",
            name=f"/Infrastructure/{get_sysenv()}/{get_stack()}/{args.name}/CONNECTION_URI",
            type="SecureString",
            value=Output.concat(
                replication_group.primary_endpoint_address,
                ":",
                replication_group.port.apply(lambda v: str(v)),
            ),
            opts=ResourceOptions(parent=replication_group),
        )

        return ElasticacheExports(
            auth_token=replication_group.auth_token,
            id=replication_group.id,
            member_clusters=replication_group.member_clusters,
            primary_endpoint_address=replication_group.primary_endpoint_address,
        )
