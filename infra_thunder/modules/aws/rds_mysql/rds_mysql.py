from pulumi import Output, ResourceOptions, get_stack
from pulumi_aws import ec2, rds, ssm
from pulumi_random.random_password import RandomPassword
from semver import VersionInfo

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import get_sysenv
from infra_thunder.lib.security_groups import (
    SecurityGroupIngressRule,
    generate_security_group_ingress_rules,
    get_default_security_groups,
)
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_tags
from infra_thunder.lib.vpc import get_vpc
from .config import MySQLExports, MySQLInstance, MySQLInstances, MySQLInstanceExport


class RDSMySQL(AWSModule):
    def build(self, config: MySQLInstances) -> list[MySQLExports]:
        self.engine = "mysql"
        vpc = get_vpc()

        subnets = get_subnets_attributes(public=False, purpose="private", vpc_id=vpc.id)
        subnet_group = rds.SubnetGroup(
            self.engine,
            description=f"{get_stack()} subnet group for {get_sysenv()}",
            subnet_ids=[subnet.id for subnet in subnets],
            tags=get_tags(get_stack(), "subnet_group"),
        )
        return [self._create_instance(instance, vpc, subnet_group) for instance in config.instances]

    def _create_instance(
        self,
        args: MySQLInstance,
        vpc: ec2.AwaitableGetVpcResult,
        subnet_group: rds.SubnetGroup,
    ) -> MySQLExports:
        instance_name = f"{self.engine}-{args.name}"
        cloudwatch_logs_exports = ["audit", "error", "general", "slowquery"]
        engine_semver = VersionInfo.parse(args.engine_version)

        parameters = [
            rds.ParameterGroupParameterArgs(
                name="max_connections",
                value="LEAST({DBInstanceClassMemory/9531392},5000)",
                apply_method="pending-reboot",
            ),
            rds.ParameterGroupParameterArgs(
                name="log_slow_admin_statements",
                value="1",
            ),
            rds.ParameterGroupParameterArgs(
                name="log_slow_slave_statements",
                value="1",
            ),
        ] + [
            rds.ParameterGroupParameterArgs(
                name=str(parameter.name),
                value=str(parameter.value),
                apply_method=parameter.apply_method,
            )
            for parameter in args.db_parameters
        ]

        parameter_group = rds.ParameterGroup(
            instance_name,
            description=f"{instance_name} instance parameter group",
            family=f"{self.engine}{engine_semver.major}.{engine_semver.minor}",
            parameters=parameters,
            tags=get_tags(get_stack(), "instance_parameters", args.name),
            opts=ResourceOptions(parent=subnet_group),
        )

        security_group = ec2.SecurityGroup(
            instance_name,
            description=f"Security Group for {instance_name} {get_sysenv()}",
            vpc_id=vpc.id,
            tags=get_tags(get_stack(), "security_group", args.name),
            opts=ResourceOptions(parent=parameter_group),
        )

        ingress_rules = [
            SecurityGroupIngressRule(
                description="RDS-MySQL",
                from_port=3306,
                to_port=3306,
                protocol="tcp",
                allow_vpc_supernet=True,
                allow_peered_supernets=True,
            ),
            SecurityGroupIngressRule(
                description="any port from self",
                from_port=0,  # all ports
                to_port=0,  # all ports
                protocol="-1",  # any
                self=True,
            ),
        ]

        generate_security_group_ingress_rules(
            rules=ingress_rules,
            security_group_id=security_group.id,
            name=instance_name,
            opts=ResourceOptions(parent=security_group),
        )

        instance_password = RandomPassword(
            instance_name,
            length=32,
            special=False,
            opts=ResourceOptions(parent=parameter_group),
        )

        ignore_changes = []
        if args.snapshot_identifier:
            ignore_changes = ["username", "storage_encrypted"]

        instance = rds.Instance(
            instance_name,
            allocated_storage=int(args.allocated_storage),
            apply_immediately=False,
            backup_retention_period=30,
            backup_window="05:00-06:00",
            db_subnet_group_name=subnet_group,
            enabled_cloudwatch_logs_exports=cloudwatch_logs_exports,
            engine_version=args.engine_version,
            final_snapshot_identifier=f"{instance_name}-final-snapshot",
            engine=self.engine,
            instance_class=args.instance_type,
            maintenance_window="sat:03:00-sat:04:00",
            multi_az=args.multi_az,
            parameter_group_name=parameter_group,
            password=instance_password.result,
            skip_final_snapshot=True,
            snapshot_identifier=args.snapshot_identifier,
            storage_encrypted=True,
            tags=get_tags(get_stack(), "instance", args.name),
            username=args.name,
            vpc_security_group_ids=[security_group.id] + get_default_security_groups(vpc_id=vpc.id).ids,
            opts=ResourceOptions(
                parent=parameter_group,
                depends_on=[instance_password],
                ignore_changes=ignore_changes,
            ),
        )

        ssm.Parameter(
            f"{instance_name}-password",
            name=f"/Infrastructure/{get_sysenv()}/{get_stack()}/{args.name}/MASTER_PASSWORD",
            type="SecureString",
            value=instance.password,
            opts=ResourceOptions(parent=instance),
        )
        ssm.Parameter(
            f"{instance_name}-connectionuri",
            name=f"/Infrastructure/{get_sysenv()}/{get_stack()}/{args.name}/CONNECTION_URI",
            type="SecureString",
            value=Output.concat(
                "mysql://",
                instance.username,
                ":",
                instance.password,
                "@",
                instance.endpoint,
                "/",
            ),
            opts=ResourceOptions(parent=instance),
        )

        replicas = [
            rds.Instance(
                f"{instance_name}-replica-{idx}",
                availability_zone=replica.availability_zone,
                backup_retention_period=0,
                enabled_cloudwatch_logs_exports=cloudwatch_logs_exports,
                final_snapshot_identifier=f"{instance_name}-replica-{idx}-final-snapshot",
                skip_final_snapshot=True,
                storage_encrypted=True,
                instance_class=args.instance_type,
                replicate_source_db=instance.identifier,
                tags=get_tags(get_stack(), "instance replica", args.name),
                opts=ResourceOptions(
                    parent=parameter_group,
                    depends_on=[instance],
                    ignore_changes=ignore_changes,
                ),
            )
            for idx, replica in enumerate(args.replicas)
        ]

        return MySQLExports(
            name=instance_name,
            instance=MySQLInstanceExport(
                address=instance.address,
                arn=instance.arn,
                endpoint=instance.endpoint,
                hosted_zone_id=instance.hosted_zone_id,
                id=instance.id,
                resource_id=instance.resource_id,
                password=instance_password.result,
                snapshot_identifier=args.snapshot_identifier,
            ),
            replicas=[
                MySQLInstanceExport(
                    address=replica.address,
                    arn=replica.arn,
                    endpoint=replica.endpoint,
                    hosted_zone_id=replica.hosted_zone_id,
                    id=replica.id,
                    resource_id=replica.resource_id,
                    password=instance_password.result,
                    snapshot_identifier=args.snapshot_identifier,
                )
                for replica in replicas
            ],
        )
