from types import SimpleNamespace

from pulumi import ComponentResource, ResourceOptions, Output
from pulumi_aws import s3, elb, athena, GetAmiResult

from infra_thunder.lib.ami import get_ami
from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import get_stack, get_sysenv, get_public_sysenv_domain
from infra_thunder.lib.iam import create_policy
from infra_thunder.lib.kubernetes import get_cluster
from infra_thunder.lib.s3 import generate_bucket_name
from infra_thunder.lib.tags import get_tags
from infra_thunder.lib.vpc import get_vpc
from .alb import create_alb
from .autoscaling_group import create_autoscaling_group
from .config import (
    K8sAgentExports,
    K8sTargetGroupExports,
    TargetGroup,
    K8sAgentConfig,
    K8sAgentArgs,
)
from .glb import create_glb, create_glb_routes
from .iam import create_nodegroup_iam_role
from .security_group import create_nodegroup_securitygroup


class K8sAgents(AWSModule):
    def __init__(self, name: str, config: K8sAgentConfig, opts: ResourceOptions = None):
        super().__init__(name, config, opts)

        self.vpc = get_vpc()

    def build(self, config: K8sAgentConfig) -> list[K8sAgentExports]:
        # Validate config - ensure every target group has at least one nodegroup associated with it!

        # Find our AMI
        ami = get_ami("ivy-kubernetes")

        # Create ALB access logs bucket and Athena DB
        log_bucket = self._create_logs_bucket(generate_bucket_name("lblogs"))
        athena_db = self._create_athena_db(generate_bucket_name("lblogs").replace("-", "_"), log_bucket)

        return [self._create_agent(agent_config, ami, log_bucket, athena_db) for agent_config in config.agents]

    def _create_agent(
        self,
        agent_config: K8sAgentArgs,
        ami: GetAmiResult,
        log_bucket: s3.Bucket,
        athena_db: athena.Database,
    ) -> K8sAgentExports:
        # if cluster name is not set we use sysenv name
        if agent_config.cluster is None:
            agent_config.cluster = get_sysenv()

        # Create component resource to group things together
        cluster_component = ComponentResource(
            f"pkg:thunder:aws:{self.__class__.__name__.lower()}:cluster:{agent_config.cluster}",
            agent_config.cluster,
            None,
            opts=ResourceOptions(parent=self),
        )

        # Get K8s control plane we're creating agents for
        controller_config = get_cluster(agent_config.cluster)

        # Create the default target group and load balancer, and route53 record
        default_tg_config = TargetGroup(
            name="default",
            ssl_domains=[f"*.{get_public_sysenv_domain()}"] + agent_config.extra_ssl_domains,
        )
        default_tg, default_alb, default_alb_acm, default_alb_dns = create_alb(
            self,
            cluster_component,
            default_tg_config,
            agent_config.cluster,
            log_bucket,
            athena_db,
        )

        # Create the extra target groups
        extra_tgs = []
        for tg_config in agent_config.extra_targetgroups:
            # normally, you'd do this in a list comprehension, however since we need to unpack a tuple
            # we have to do it the long way (code golf is fun, but I prefer readable code)
            tg, alb, acm, dns = create_alb(
                self,
                cluster_component,
                tg_config,
                agent_config.cluster,
                log_bucket,
                athena_db,
            )
            extra_tgs.append(SimpleNamespace(name=tg_config.name, tg=tg, alb=alb, acm=acm, dns=dns))

        # Create the GLB and add it to the route table for the cluster's serviceCIDR
        if agent_config.enable_glb:
            glb_tg, glb, ep = create_glb(self, cluster_component, agent_config.cluster)
            create_glb_routes(self, controller_config, ep)

        # Create the IAM role for the nodegroups
        instance_profile, instance_role = create_nodegroup_iam_role(
            self, cluster_component, agent_config.cluster, controller_config
        )

        # Create custom policies and attach them to instance_role
        for policy in agent_config.custom_iam_policies:
            create_policy(self, policy, instance_role)

        # Create security group for the nodegroups
        security_group = create_nodegroup_securitygroup(cluster_component, agent_config.cluster)

        # Customize cluster to add ingress
        # TODO: add ingresses (ingressii?)

        for nodegroup in agent_config.nodegroups:
            # Create the launch template and wire it up to the appropriate target groups
            nodegroup_tgs = list(
                map(
                    lambda x: x.tg,
                    filter(lambda y: y.name in nodegroup.extra_targetgroups, extra_tgs),
                )
            )
            if nodegroup.include_default_targetgroup:
                nodegroup_tgs.append(default_tg)
            create_autoscaling_group(
                self,
                cluster_component,
                agent_config,
                nodegroup,
                ami,
                nodegroup_tgs,
                instance_profile,
                security_group,
                controller_config,
            )

        return K8sAgentExports(
            cluster=agent_config.cluster,
            role_arn=instance_role.arn,
            default_targetgroup=K8sTargetGroupExports(
                name="default",
                id=default_tg.id,
                dns_name=default_alb_dns.name,
                acm_certificate_arn=default_alb_acm.arn,
                acm_ssl_validation_records=default_alb_acm.domain_validation_options,
            ),
            extra_targetgroups=[
                K8sTargetGroupExports(
                    name=extra_tg.name,
                    id=extra_tg.tg.id,
                    dns_name=extra_tg.dns.name,
                    acm_certificate_arn=extra_tg.acm.arn,
                    acm_ssl_validation_records=extra_tg.acm.domain_validation_options,
                )
                for extra_tg in extra_tgs
            ],
            nodegroups=[nodegroup.name for nodegroup in agent_config.nodegroups],
        )

    def _create_logs_bucket(self, bucket_name: str) -> s3.Bucket:
        # TODO: create lifecycle rules
        bucket = s3.Bucket(
            bucket_name,
            bucket=bucket_name,
            acl="private",
            versioning=s3.BucketVersioningArgs(enabled=False),
            tags=get_tags(get_stack(), "bucket", bucket_name),
            opts=ResourceOptions(parent=self),
        )
        s3.BucketPolicy(
            bucket_name,
            bucket=bucket.id,
            policy={
                "Version": "2012-10-17",
                "Id": f"{bucket_name}-elb-logs",
                "Statement": [
                    {
                        "Sid": f"{bucket_name}-aws-lb-logs",
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": elb.get_service_account(self.region).arn,
                        },
                        "Action": [
                            "s3:PutObject",
                        ],
                        "Resource": [
                            Output.concat(bucket.arn, "/*"),
                        ],
                    },
                    {
                        "Sid": f"{bucket_name}-aws-logdelivery-put",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "delivery.logs.amazonaws.com",
                        },
                        "Action": [
                            "s3:PutObject",
                        ],
                        "Resource": [
                            Output.concat(bucket.arn, "/*"),
                        ],
                        "Condition": {
                            "StringEquals": {
                                "s3:x-amz-acl": "bucket-owner-full-control",
                            }
                        },
                    },
                    {
                        "Sid": f"{bucket_name}-aws-logdelivery-getacl",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "delivery.logs.amazonaws.com",
                        },
                        "Action": [
                            "s3:GetBucketAcl",
                        ],
                        "Resource": [
                            bucket.arn,
                        ],
                    },
                ],
            },
            opts=ResourceOptions(parent=bucket),
        )
        s3.BucketPublicAccessBlock(
            bucket_name,
            bucket=bucket.id,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
            opts=ResourceOptions(parent=bucket),
        )
        return bucket

    def _create_athena_db(self, db_name: str, log_bucket: s3.Bucket) -> athena.Database:
        db = athena.Database(db_name, bucket=log_bucket, opts=ResourceOptions(parent=log_bucket))
        athena.Workgroup(
            db_name,
            configuration=athena.WorkgroupConfigurationArgs(
                enforce_workgroup_configuration=True,
                publish_cloudwatch_metrics_enabled=True,
                result_configuration=athena.WorkgroupConfigurationResultConfigurationArgs(
                    output_location=Output.concat(
                        "s3://",
                        log_bucket.bucket,
                        f"/athena/{get_stack()}/",
                    ),
                ),
            ),
            opts=ResourceOptions(parent=db),
        )
        return db
