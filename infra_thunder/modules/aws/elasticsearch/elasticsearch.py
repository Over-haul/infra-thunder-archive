from pulumi import ResourceOptions, Output
from pulumi_aws import elasticsearch, iam

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.security_groups import (
    generate_security_group,
    SecurityGroupIngressRule,
    get_default_security_groups,
)
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_tags
from .config import (
    ClusterConfig,
    ClusterExports,
    ElasticSearchConfig,
    ElasticSearchExports,
)


class ElasticSearch(AWSModule):
    def build(self, config: ElasticSearchConfig) -> ElasticSearchExports:
        iam.ServiceLinkedRole(
            "elasticsearch",
            aws_service_name="es.amazonaws.com",
            opts=ResourceOptions(parent=self),
        )

        security_group = generate_security_group(
            name="elasticsearch-common",
            ingress_rules=[
                SecurityGroupIngressRule(
                    description="Allow ES traffic",
                    from_port=443,
                    to_port=443,
                    protocol="tcp",
                    allow_vpc_supernet=True,
                    allow_peered_supernets=True,
                )
            ],
            opts=ResourceOptions(parent=self),
        )

        security_group_ids = [security_group.id] + get_default_security_groups().ids
        subnet_ids = [s.id for s in get_subnets_attributes(public=False, purpose="private")]

        # number of availability zones is always equal to the number of subnets
        availability_zones_count = len(subnet_ids)

        return ElasticSearchExports(
            clusters=[
                self._build_cluster(
                    config=cluster_config,
                    security_group_ids=security_group_ids,
                    subnet_ids=subnet_ids,
                    availability_zones_count=availability_zones_count,
                )
                for cluster_config in config.clusters
            ],
        )

    def _build_cluster(
        self,
        config: ClusterConfig,
        security_group_ids: list[Output[str]],
        subnet_ids: list[str],
        availability_zones_count: int,
    ) -> ClusterExports:
        if config.dedicated_master_type:
            dedicated_master_args = elasticsearch.DomainClusterConfigArgs(
                dedicated_master_enabled=True,
                dedicated_master_type=config.dedicated_master_type,
                dedicated_master_count=3,
            )
        else:
            dedicated_master_args = elasticsearch.DomainClusterConfigArgs(
                dedicated_master_enabled=False,
            )

        cluster = elasticsearch.Domain(
            config.name,
            domain_name=config.name,
            elasticsearch_version=config.elasticsearch_version,
            cluster_config=elasticsearch.DomainClusterConfigArgs(
                instance_count=config.instance_count_per_zone * availability_zones_count,
                instance_type=config.instance_type,
                zone_awareness_enabled=True,
                zone_awareness_config=elasticsearch.DomainClusterConfigZoneAwarenessConfigArgs(
                    availability_zone_count=availability_zones_count,
                ),
                warm_enabled=False,
                **dedicated_master_args.__dict__,
            ),
            ebs_options=elasticsearch.DomainEbsOptionsArgs(
                ebs_enabled=True,
                volume_size=config.ebs_volume_size,
                volume_type="gp2",
            ),
            vpc_options=elasticsearch.DomainVpcOptionsArgs(
                security_group_ids=security_group_ids,
                subnet_ids=subnet_ids,
            ),
            access_policies={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": "es:*",
                        "Resource": "*",
                    }
                ],
            }
            if config.disable_authentication
            else None,
            advanced_options=config.advanced_options,
            tags=get_tags(service="elasticsearch", role="domain", group=config.name),
            opts=ResourceOptions(parent=self, ignore_changes=["advancedOptions"]),
        )

        return ClusterExports(
            name=config.name,
            arn=cluster.arn,
            domain_id=cluster.domain_id,
            endpoint=cluster.endpoint,
            id=cluster.id,
        )
