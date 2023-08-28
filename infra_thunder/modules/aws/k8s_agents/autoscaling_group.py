from pulumi import ResourceOptions, ComponentResource, Output
from pulumi_aws import ec2, autoscaling, lb, iam, GetAmiResult

from infra_thunder.lib.aws.kubernetes import get_ssm_path
from infra_thunder.lib.config import get_stack
from infra_thunder.lib.config import tag_prefix, tag_namespace
from infra_thunder.lib.keypairs import get_keypair
from infra_thunder.lib.kubernetes.constants import (
    MONITORING_SECRET_NAME,
    SPOT_TAG_KEY,
    SPOT_TAG_VALUE,
    DEDICATED_TAG_KEY,
    DEDICATED_TAG_VALUE,
    NODEGROUP_TAG_KEY,
    NODEGROUP_TAG_VALUE,
)
from infra_thunder.lib.security_groups import get_default_security_groups
from infra_thunder.lib.ssm import PARAMETER_STORE_BASE
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_tags, get_asg_tags, get_sysenv
from infra_thunder.lib.user_data import UserData
from .config import K8sAgentArgs, NodeGroup


def create_autoscaling_group(
    cls,
    dependency: ComponentResource,
    agent_config: K8sAgentArgs,
    nodegroup: NodeGroup,
    ami: GetAmiResult,
    target_groups: list[lb.TargetGroup],
    instance_profile: iam.InstanceProfile,
    security_group: ec2.SecurityGroup,
    cluster_config: Output,
):
    resource_name = f"{get_stack()}-{agent_config.cluster}-{nodegroup.name}"

    asg_tags = [
        *get_asg_tags(get_stack(), agent_config.cluster, nodegroup.name),
        {
            "key": f"{tag_prefix}{NODEGROUP_TAG_KEY}",
            "propagateAtLaunch": True,
            "value": NODEGROUP_TAG_VALUE,
        },
    ]

    lt_tags = get_tags(get_stack(), agent_config.cluster, nodegroup.name)
    taints = []
    if nodegroup.spot_instances:
        taints.append(f"{tag_namespace}/{SPOT_TAG_KEY}={SPOT_TAG_VALUE}:NoSchedule")
        lt_tags[f"{tag_prefix}{SPOT_TAG_KEY}"] = SPOT_TAG_VALUE
        asg_tags.append(
            {
                "key": f"{tag_prefix}{SPOT_TAG_KEY}",
                "propagateAtLaunch": True,
                "value": SPOT_TAG_VALUE,
            }
        )
    if nodegroup.dedicated:
        taints.append(f"{tag_namespace}/{DEDICATED_TAG_KEY}={nodegroup.name}:NoSchedule")
        lt_tags[f"{tag_prefix}{DEDICATED_TAG_KEY}"] = DEDICATED_TAG_VALUE
        asg_tags.append(
            {
                "key": f"{tag_prefix}{DEDICATED_TAG_KEY}",
                "propagateAtLaunch": True,
                "value": DEDICATED_TAG_VALUE,
            }
        )

    lt = ec2.LaunchTemplate(
        resource_name,
        update_default_version=True,
        iam_instance_profile=ec2.LaunchTemplateIamInstanceProfileArgs(arn=instance_profile.arn),
        ebs_optimized=True,
        key_name=get_keypair(),
        block_device_mappings=[
            # Rootfs size
            ec2.LaunchTemplateBlockDeviceMappingArgs(
                device_name="/dev/xvda",
                ebs=ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                    delete_on_termination=True,
                    volume_size=nodegroup.rootfs_size_gb,
                ),
            ),
            # Docker volume
            ec2.LaunchTemplateBlockDeviceMappingArgs(
                device_name="/dev/xvdb",
                ebs=ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                    delete_on_termination=True,
                    volume_size=nodegroup.dockervol_size_gb,
                    volume_type=nodegroup.dockervol_type,
                ),
            ),
        ],
        user_data=UserData(
            resource_name,
            include_defaults=True,
            include_cloudconfig=True,
            base64_encode=True,
            replacements={
                "endpoint_name": cluster_config["endpoint"],
                # TODO: extract this
                "ssm_params": [
                    (
                        "pki/ca.crt",
                        f"{PARAMETER_STORE_BASE}/{get_sysenv()}/{get_ssm_path(agent_config.cluster)}/pki/ca.crt",
                    )
                ],
                "cluster_name": agent_config.cluster,
                "cluster_domain": cluster_config["cluster_domain"],
                "cluster_dns": cluster_config["coredns_clusterip"],
                "service_cidr": cluster_config["service_cidr"],
                "nodegroup": nodegroup.name,
                "bootstrap_role_arn": cluster_config["bootstrap_role_arn"],
                "monitoring_secret": MONITORING_SECRET_NAME,
                "taints": taints,
                "docker_registry_cache": agent_config.docker_registry_cache,
            },
            opts=ResourceOptions(parent=dependency),
        ).template,
        image_id=ami.id,
        instance_type=nodegroup.instance_type,
        vpc_security_group_ids=[security_group] + get_default_security_groups(vpc_id=cls.vpc.id).ids,
        tags=lt_tags,
        tag_specifications=[
            ec2.LaunchTemplateTagSpecificationArgs(resource_type="instance", tags=lt_tags),
            ec2.LaunchTemplateTagSpecificationArgs(resource_type="volume", tags=lt_tags),
        ],
        opts=ResourceOptions(parent=instance_profile),
    )

    launch_template = None
    mixed_instances_policy = None

    if nodegroup.spot_instances:
        mixed_instances_policy = autoscaling.GroupMixedInstancesPolicyArgs(
            instances_distribution=autoscaling.GroupMixedInstancesPolicyInstancesDistributionArgs(
                on_demand_allocation_strategy="prioritized",
                on_demand_base_capacity=0,
                on_demand_percentage_above_base_capacity=0,
                spot_allocation_strategy="capacity-optimized",
                spot_instance_pools=0,
                spot_max_price="",
            ),
            launch_template=autoscaling.GroupMixedInstancesPolicyLaunchTemplateArgs(
                launch_template_specification=autoscaling.GroupMixedInstancesPolicyLaunchTemplateLaunchTemplateSpecificationArgs(
                    launch_template_id=lt.id, version="$Latest"
                ),
                overrides=[
                    autoscaling.GroupMixedInstancesPolicyLaunchTemplateOverrideArgs(
                        instance_type=nodegroup.instance_type
                    )
                ],
            ),
        )
    else:
        launch_template = autoscaling.GroupLaunchTemplateArgs(id=lt.id, version="$Latest")

    asg = autoscaling.Group(
        resource_name,
        launch_template=launch_template,
        mixed_instances_policy=mixed_instances_policy,
        vpc_zone_identifiers=[
            subnet.id for subnet in get_subnets_attributes(public=False, purpose="private", vpc_id=cls.vpc.id)
        ],
        suspended_processes=[
            "ReplaceUnhealthy",
        ],
        health_check_type="EC2",
        health_check_grace_period=300,
        target_group_arns=[tg.id for tg in target_groups],
        min_size=nodegroup.min_size,
        max_size=nodegroup.max_size,
        tags=asg_tags,
        opts=ResourceOptions(parent=lt),
    )

    # lifecycle hook for launching instances
    autoscaling.LifecycleHook(
        f"{resource_name}-at-launch",
        autoscaling_group_name=asg.name,
        default_result="ABANDON",
        heartbeat_timeout=900,
        lifecycle_transition="autoscaling:EC2_INSTANCE_LAUNCHING",
        opts=ResourceOptions(parent=asg),
    )

    # lifecycle hook for terminating instances
    autoscaling.LifecycleHook(
        f"{resource_name}-at-termination",
        autoscaling_group_name=asg.name,
        default_result="CONTINUE",
        heartbeat_timeout=300,
        lifecycle_transition="autoscaling:EC2_INSTANCE_TERMINATING",
        opts=ResourceOptions(parent=asg),
    )
