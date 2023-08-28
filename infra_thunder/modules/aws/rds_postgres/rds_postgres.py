from collections import defaultdict
from pulumi import Output, ResourceOptions, get_stack, log
from pulumi_aws import ec2, rds, ssm
from pulumi_postgresql import database, default_privileges, grant, grant_role, provider, role
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
from .config import RDSExports, RDSInstance, RDSInstances, RDSInstanceExport


class RDSPostgres(AWSModule):
    def build(self, config: RDSInstances) -> list[RDSExports]:
        self.engine = "postgres"
        self.db_roles = ["app", "read"]
        vpc = get_vpc()

        subnets = get_subnets_attributes(public=False, purpose="private", vpc_id=vpc.id)
        subnet_group = rds.SubnetGroup(
            get_stack(),
            description=f"{get_stack()} subnet group for {get_sysenv()}",
            subnet_ids=[subnet.id for subnet in subnets],
            tags=get_tags(get_stack(), "subnet_group"),
        )
        return [self._create_instance(instance, vpc, subnet_group) for instance in config.instances]

    def _create_instance(
        self,
        args: RDSInstance,
        vpc: ec2.AwaitableGetVpcResult,
        subnet_group: rds.SubnetGroup,
    ) -> RDSExports:
        instance_name = f"{self.engine}-{args.name}"
        engine_semver = VersionInfo.parse(args.engine_version)

        parameters = [
            rds.ParameterGroupParameterArgs(
                name="max_connections",
                value="LEAST({DBInstanceClassMemory/9531392},5000)",
                apply_method="pending-reboot",
            ),
            rds.ParameterGroupParameterArgs(
                name="log_min_duration_statement",
                value="250",
            ),
            rds.ParameterGroupParameterArgs(
                name="pg_stat_statements.track",
                value="all",
            ),
            rds.ParameterGroupParameterArgs(
                name="pg_stat_statements.max",
                value="1000",
                apply_method="pending-reboot",
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
            family=f"{self.engine}{engine_semver.major}",
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
                description="RDS",
                from_port=5432,
                to_port=5432,
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
            enabled_cloudwatch_logs_exports=[
                "upgrade",
                "postgresql",
            ],  # options: agent alert audit error general listener slowquery trace postgresql upgrade
            engine_version=f"{engine_semver.major}.{engine_semver.minor}",
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
                "postgres://",
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
                enabled_cloudwatch_logs_exports=[
                    "upgrade",
                    "postgresql",
                ],  # options: agent alert audit error general listener slowquery trace postgresql upgrade
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

        # Create databases within the instance
        pg_provider = provider.Provider(
            f"{instance_name}-pg-provider",
            host=instance.address,
            port=instance.port,
            username=instance.username,
            password=instance.password,
            superuser=False,
            opts=ResourceOptions(parent=instance, depends_on=[instance] + replicas),
        )
        databases: dict = {}
        for db_name in args.databases:
            if int(engine_semver.major) >= 14:
                databases = self._setup_database(instance_name, args.name, db_name, pg_provider)
            else:
                log.warn(
                    f"Creation of databases is only supported for PostgreSQL version 14 or higher. Engine version: {args.engine_version}.",
                    pg_provider,
                )

        return RDSExports(
            name=instance_name,
            instance=RDSInstanceExport(
                address=instance.address,
                arn=instance.arn,
                endpoint=instance.endpoint,
                hosted_zone_id=instance.hosted_zone_id,
                id=instance.id,
                resource_id=instance.resource_id,
                password=instance_password.result,
                snapshot_identifier=args.snapshot_identifier,
                databases=databases,
            ),
            replicas=[
                RDSInstanceExport(
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

    def _setup_database(
        self, instance_name: str, instance_username: str, db_name: str, pg_provider: provider.Provider
    ) -> dict:
        db, dep_grant = self._create_database(instance_name, instance_username, db_name, pg_provider)
        databases = defaultdict(dict)
        deps = [dep_grant]
        for role_name in self.db_roles:
            name_of_role, role_password, rname, dep = self._create_role(
                instance_name, db_name, role_name, db, deps, pg_provider
            )
            deps.append(dep)
            databases[db_name][name_of_role] = role_password
        return databases

    def _create_database(
        self, instance_name: str, instance_username: str, db_name: str, pg_provider: provider.Provider
    ) -> (database.Database, grant.Grant):
        db = database.Database(
            f"{instance_name}-{db_name}",
            name=db_name,
            opts=ResourceOptions(parent=pg_provider, provider=pg_provider),
        )
        grant_all_db = grant.Grant(
            f"{instance_name}-{db_name}-grant-all-to-{instance_username}",
            database=db.name,
            role=instance_username,
            object_type="database",
            privileges=["CREATE", "CONNECT", "TEMPORARY"],
            opts=ResourceOptions(parent=db, provider=pg_provider),
        )
        revoke_all_schema = grant.Grant(
            f"{instance_name}-{db_name}-revoke-all-from-public",
            database=db.name,
            role="public",
            object_type="schema",
            schema="public",
            privileges=[],
            opts=ResourceOptions(parent=grant_all_db, provider=pg_provider),
        )
        revoke_all_db = grant.Grant(
            f"{instance_name}-{db_name}-revoke-all-from-db",
            database=db.name,
            role="public",
            object_type="database",
            privileges=[],
            opts=ResourceOptions(parent=revoke_all_schema, provider=pg_provider),
        )

        return db, revoke_all_db

    def _create_role(
        self,
        instance_name: str,
        db_name: str,
        role_name: str,
        db: database.Database,
        deps: list,
        pg_provider: provider.Provider,
    ) -> (str, str, role.Role, default_privileges.DefaultPrivileges):
        role_password = RandomPassword(
            f"{instance_name}-{db_name}-{role_name}-password",
            length=32,
            special=False,
            opts=ResourceOptions(parent=db),
        )
        name_of_role = f"{db_name}_{role_name}"
        rname = role.Role(
            f"{instance_name}-{db_name}-{role_name}",
            name=name_of_role,
            password=role_password.result,
            login=True,
            opts=ResourceOptions(parent=db, provider=pg_provider, depends_on=deps[-1:]),
        )
        grant_connect = grant.Grant(
            f"{instance_name}-{db_name}-grant-connect-to-{name_of_role}",
            database=db.name,
            role=rname.name,
            object_type="database",
            privileges=["CONNECT"],
            opts=ResourceOptions(parent=rname, provider=pg_provider),
        )
        dep = grant_role.GrantRole(
            f"{instance_name}-{db_name}-{role_name}-grant-read-to",
            role=rname.name,
            grant_role="pg_read_all_data",
            opts=ResourceOptions(parent=grant_connect, provider=pg_provider),
        )
        if role_name == "app":
            dep = self._grant_app_access(instance_name, db_name, db, rname, dep, pg_provider)
        return name_of_role, role_password.result, rname, dep

    def _grant_app_access(
        self,
        instance_name: str,
        db_name: str,
        db: database.Database,
        rname: role.Role,
        dep: grant_role.GrantRole,
        pg_provider: provider.Provider,
    ) -> grant_role.GrantRole:
        grant_all_db = grant.Grant(
            f"{instance_name}-{db_name}-app-grant-db",
            database=db.name,
            role=rname.name,
            object_type="database",
            privileges=["CONNECT", "CREATE", "TEMPORARY"],
            opts=ResourceOptions(parent=dep, provider=pg_provider),
        )
        grant_all_schema = grant.Grant(
            f"{instance_name}-{db_name}-app-grant-schema",
            database=db.name,
            role=rname.name,
            object_type="schema",
            schema="public",
            privileges=["CREATE", "USAGE"],
            opts=ResourceOptions(parent=grant_all_db, provider=pg_provider),
        )

        return grant_role.GrantRole(
            f"{instance_name}-{db_name}-app-grant-write",
            role=rname.name,
            grant_role="pg_write_all_data",
            opts=ResourceOptions(parent=grant_all_schema, provider=pg_provider),
        )
