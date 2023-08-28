from pulumi import ResourceOptions, Output
from pulumi_aws import docdb, ec2, ssm
from pulumi_random import RandomPassword
from semver import VersionInfo

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import get_sysenv, get_stack
from infra_thunder.lib.security_groups import (
    get_default_security_groups,
    SecurityGroupIngressRule,
    generate_security_group,
)
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_tags
from infra_thunder.lib.vpc import get_vpc
from .config import Cluster, DocumentDBArgs, DocumentDBExports


class DocumentDB(AWSModule):
    def build(self, config: DocumentDBArgs) -> list[DocumentDBExports]:
        vpc = get_vpc()

        subnets = get_subnets_attributes(public=False, purpose="private", vpc_id=vpc.id)
        subnet_group = docdb.SubnetGroup(
            get_stack(),
            description=f"{get_stack()} subnet group for {get_sysenv()}",
            subnet_ids=[subnet.id for subnet in subnets],
            tags=get_tags(get_stack(), "subnet_group"),
        )

        return [self._create_cluster(cluster, vpc, subnet_group) for cluster in config.clusters]

    def _create_cluster(
        self,
        args: Cluster,
        vpc: ec2.AwaitableGetVpcResult,
        subnet_group: docdb.SubnetGroup,
    ) -> DocumentDBExports:
        cluster_name = f"{get_stack()}-{args.name}"
        engine = "docdb"
        engine_semver = VersionInfo.parse(args.engine_version)

        parameters = []
        if args.cluster_parameters:
            parameters = [
                docdb.ClusterParameterGroupParameterArgs(
                    name=parameter.name,
                    value=parameter.value,
                )
                for parameter in args.cluster_parameters
            ]

        parameter_group = docdb.ClusterParameterGroup(
            cluster_name,
            name_prefix=args.name,
            description=f"{cluster_name} cluster parameter group",
            family=f"{engine}{engine_semver.major}.{engine_semver.minor}",
            parameters=parameters,
            tags=get_tags(get_stack(), "cluster_parameters", args.name),
            opts=ResourceOptions(parent=subnet_group),
        )

        ingress_rules = [
            SecurityGroupIngressRule(
                description="MongoDB",
                from_port=27017,
                to_port=27017,
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
            name=cluster_name,
            opts=ResourceOptions(parent=self),
        )

        cluster_password = RandomPassword(
            cluster_name,
            length=32,
            special=False,
            opts=ResourceOptions(parent=parameter_group),
        )

        cluster = docdb.Cluster(
            cluster_name,
            backup_retention_period=5,
            cluster_identifier_prefix=args.name,
            db_subnet_group_name=subnet_group,
            db_cluster_parameter_group_name=parameter_group,
            engine=engine,
            engine_version=args.engine_version,
            master_username=args.name,
            master_password=cluster_password.result,
            preferred_backup_window="06:00-07:00",
            preferred_maintenance_window="sat:07:00-sat:08:00",
            skip_final_snapshot=True,
            apply_immediately=False,
            storage_encrypted=True,
            enabled_cloudwatch_logs_exports=["audit", "profiler"],
            vpc_security_group_ids=[security_group.id] + get_default_security_groups(vpc_id=vpc.id).ids,
            tags=get_tags(get_stack(), "cluster", args.name),
            opts=ResourceOptions(parent=parameter_group, depends_on=[cluster_password]),
        )
        ssm.Parameter(
            f"{cluster_name}-password",
            name=f"/Infrastructure/{get_sysenv()}/{get_stack()}/{args.name}/MASTER_PASSWORD",
            type="SecureString",
            value=cluster.master_password,
            opts=ResourceOptions(parent=cluster),
        )
        ssm.Parameter(
            f"{cluster_name}-connectionuri",
            name=f"/Infrastructure/{get_sysenv()}/{get_stack()}/{args.name}/CONNECTION_URI",
            type="SecureString",
            value=Output.concat(
                "mongodb://",
                cluster.master_username,
                ":",
                cluster.master_password,
                "@",
                cluster.endpoint,
                ":",
                cluster.port,
                "/",
            ),
            opts=ResourceOptions(parent=cluster),
        )
        instances = [
            docdb.ClusterInstance(
                f"{cluster_name}-{index}",
                apply_immediately=False,
                auto_minor_version_upgrade=True,
                cluster_identifier=cluster.cluster_resource_id,
                engine=engine,
                identifier_prefix=f"{args.name}-{index}",
                instance_class=args.instance_type,
                preferred_maintenance_window="sat:08:00-sat:09:00",
                tags=get_tags(get_stack(), "instance", args.name),
                opts=ResourceOptions(parent=cluster),
            )
            for index in range(args.count)
        ]
        return DocumentDBExports(
            arn=cluster.arn,
            cluster_resource_id=cluster.cluster_resource_id,
            endpoint=cluster.endpoint,
            hosted_zone_id=cluster.hosted_zone_id,
            id=cluster.id,
            reader_endpoint=cluster.reader_endpoint,
            instances_arn=[instance.arn for instance in instances],
            master_username=cluster.master_username,
            master_password=cluster.master_password,
        )
