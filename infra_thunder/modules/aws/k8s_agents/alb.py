from pulumi import ResourceOptions, ComponentResource, Output
from pulumi_aws import athena, ec2, glue, lb, route53, s3, acm

from infra_thunder.lib.config import get_stack, get_public_sysenv_domain, get_sysenv
from infra_thunder.lib.security_groups import (
    get_default_security_groups,
    ANY_IPV4_ADDRESS,
)
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_tags
from .config import TargetGroup
from .generate_lb_name import generate_lb_name


def create_alb(
    cls,
    dependency: ComponentResource,
    tg_config: TargetGroup,
    cluster_name: str,
    log_bucket: s3.Bucket,
    athena_db: athena.Database,
) -> (lb.TargetGroup, lb.LoadBalancer, acm.Certificate, route53.Record):
    if cluster_name == get_sysenv():
        resource_name = tg_config.name
    else:
        resource_name = f"{cluster_name}-{tg_config.name}"
    short_resource_name = generate_lb_name(cluster_name, tg_config.name)

    sysenv_domain = get_public_sysenv_domain()
    zone_id = route53.get_zone(name=sysenv_domain).id

    tg = lb.TargetGroup(
        # taget groups max out at 32 chars, shorten it to fit
        f"{short_resource_name}-tg",
        port=8080,
        protocol="HTTP",
        vpc_id=cls.vpc.id,
        health_check=lb.TargetGroupHealthCheckArgs(
            port="9000",
            protocol="HTTP",
            path="/ping",
            interval=15,
            unhealthy_threshold=2,
        ),
        deregistration_delay=30,
        tags=get_tags(get_stack(), cluster_name, tg_config.name),
        opts=ResourceOptions(parent=dependency),
    )

    alb_sg = ec2.SecurityGroup(
        f"{resource_name}-alb-sg",
        ingress=[
            ec2.SecurityGroupIngressArgs(
                description="Allow HTTP inbound from the Internet",
                from_port=80,
                to_port=80,
                protocol="tcp",
                cidr_blocks=[ANY_IPV4_ADDRESS],
            ),
            ec2.SecurityGroupIngressArgs(
                description="Allow HTTPS inbound from the Internet",
                from_port=443,
                to_port=443,
                protocol="tcp",
                cidr_blocks=[ANY_IPV4_ADDRESS],
            ),
        ],
        vpc_id=cls.vpc.id,
        tags=get_tags(get_stack(), cluster_name, tg_config.name),
        opts=ResourceOptions(parent=dependency),
    )

    if tg_config.acm_cert_arn:
        acm_cert_arn = tg_config.acm_cert_arn
        acm_cert = None
    else:
        # Take first domain, if it's a wildcard strip the wildcard off and use it
        primary_domain_name = tg_config.ssl_domains[0].removeprefix("*.")
        acm_cert = acm.Certificate(
            f"{short_resource_name}-acm",
            domain_name=primary_domain_name,
            validation_method="DNS",
            subject_alternative_names=tg_config.ssl_domains,
            tags=get_tags(get_stack(), cluster_name, tg_config.name),
            opts=ResourceOptions(parent=tg),
        )
        acm_cert_arn = acm_cert.arn

        # create the validation records we can get a reference to the route53 zone where the record would live
        if primary_domain_name == get_public_sysenv_domain():
            acm_record = acm_cert.domain_validation_options.apply(
                lambda dv: list(filter(lambda v: v.domain_name == get_public_sysenv_domain(), dv))
            )[0]
            acm_validation_records = acm_cert.domain_validation_options.apply(
                lambda dv: list(map(lambda v: v.resource_record_name, dv))
            )
            r53_record = route53.Record(
                f"{short_resource_name}-acm",
                zone_id=zone_id,
                allow_overwrite=True,
                name=acm_record.resource_record_name,
                records=[acm_record.resource_record_value],
                ttl=60,
                type=acm_record.resource_record_type,
                opts=ResourceOptions(parent=acm_cert),
            )
            acm.CertificateValidation(
                f"{short_resource_name}-acm",
                certificate_arn=acm_cert.arn,
                validation_record_fqdns=acm_validation_records,
                opts=ResourceOptions(parent=r53_record),
            )

    alb = lb.LoadBalancer(
        f"{short_resource_name}-alb",
        internal=False,
        load_balancer_type="application",
        security_groups=[alb_sg] + get_default_security_groups(cls.vpc.id).ids,
        subnets=[subnet.id for subnet in get_subnets_attributes(public=True, purpose="public", vpc_id=cls.vpc.id)],
        access_logs=lb.LoadBalancerAccessLogsArgs(
            bucket=log_bucket.bucket,
            prefix=f"{cluster_name}-{tg_config.name}",
            enabled=True,
        ),
        tags=get_tags(get_stack(), cluster_name, tg_config.name),
        opts=ResourceOptions(parent=tg),
    )

    lb.Listener(
        f"{short_resource_name}-HTTPS",
        load_balancer_arn=alb.arn,
        port=443,
        protocol="HTTPS",
        ssl_policy="ELBSecurityPolicy-2016-08",
        certificate_arn=acm_cert_arn,
        default_actions=[
            lb.ListenerDefaultActionArgs(
                type="forward",
                target_group_arn=tg.arn,
            )
        ],
        opts=ResourceOptions(parent=alb),
    )

    lb.Listener(
        f"{short_resource_name}-HTTP-to-HTTPS",
        load_balancer_arn=alb.arn,
        port=80,
        protocol="HTTP",
        default_actions=[
            lb.ListenerDefaultActionArgs(
                type="redirect",
                redirect=lb.ListenerDefaultActionRedirectArgs(
                    port="443",
                    protocol="HTTPS",
                    status_code="HTTP_301",
                ),
            )
        ],
        opts=ResourceOptions(parent=alb),
    )

    glue.CatalogTable(
        resource_name,
        database_name=athena_db.id,
        description=f"{resource_name} load balancer access logs",
        table_type="EXTERNAL_TABLE",
        storage_descriptor=glue.CatalogTableStorageDescriptorArgs(
            location=Output.concat(
                "s3://",
                log_bucket.bucket,
                f"/{cluster_name}-{tg_config.name}/AWSLogs/",
                cls.aws_account_id,
                "/elasticloadbalancing/",
                cls.region,
            ),
            input_format="org.apache.hadoop.mapred.TextInputFormat",
            output_format="org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
            ser_de_info=glue.CatalogTableStorageDescriptorSerDeInfoArgs(
                name=f"{resource_name}-alb-logs",
                serialization_library="org.apache.hadoop.hive.serde2.RegexSerDe",
                parameters={
                    "serialization.format": 1,
                    "input.regex": '([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*):([0-9]*) ([^ ]*)[:-]([0-9]*) ([-.0-9]*) ([-.0-9]*) ([-.0-9]*) (|[-0-9]*) (-|[-0-9]*) ([-0-9]*) ([-0-9]*) "([^ ]*) ([^ ]*) (- |[^ ]*)" "([^"]*)" ([A-Z0-9-]+) ([A-Za-z0-9.-]*) ([^ ]*) "([^"]*)" "([^"]*)" "([^"]*)" ([-.0-9]*) ([^ ]*) "([^"]*)" "([^"]*)" "([^ ]*)" "([^\s]+?)" "([^\s]+)" "([^ ]*)" "([^ ]*)"',
                },
            ),
            columns=[
                glue.CatalogTableStorageDescriptorColumnArgs(name="type", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="time", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="elb", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="client_ip", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="client_port", type="int"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="target_ip", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="target_port", type="int"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="request_processing_time", type="double"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="target_processing_time", type="double"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="response_processing_time", type="double"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="elb_status_code", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="target_status_code", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="received_bytes", type="bigint"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="sent_bytes", type="bigint"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="request_verb", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="request_url", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="request_proto", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="user_agent", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="ssl_cipher", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="ssl_protocol", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="target_group_arn", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="trace_id", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="domain_name", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="chosen_cert_arn", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="matched_rule_priority", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="request_creation_time", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="actions_executed", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="redirect_url", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="lambda_error_reason", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="target_port_list", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="target_status_code_list", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="classification", type="string"),
                glue.CatalogTableStorageDescriptorColumnArgs(name="classification_reason", type="string"),
            ],
        ),
        parameters={"EXTERNAL": "TRUE"},
        opts=ResourceOptions(parent=athena_db, depends_on=[alb]),
    )

    dns = route53.Record(
        short_resource_name,
        zone_id=zone_id,
        name=f"{resource_name}.{sysenv_domain}",
        type="A",
        aliases=[
            route53.RecordAliasArgs(
                evaluate_target_health=False,
                name=alb.dns_name,
                zone_id=alb.zone_id,
            )
        ],
        opts=ResourceOptions(parent=alb),
    )

    return tg, alb, acm_cert, dns
