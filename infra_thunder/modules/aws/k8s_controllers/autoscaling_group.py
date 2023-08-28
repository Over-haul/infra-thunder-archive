import ipaddress

from pulumi import ComponentResource, ResourceOptions, Output
from pulumi_aws import GetAmiResult, iam, ec2, ssm, autoscaling

from infra_thunder.lib.keypairs import get_keypair
from infra_thunder.lib.security_groups import get_default_security_groups
from infra_thunder.lib.tags import get_tags, get_stack, get_asg_tags
from infra_thunder.lib.user_data import UserData
from .config import K8sControllerArgs


def create_autoscaling_group(
    cls,
    dependency: ComponentResource,
    ami: GetAmiResult,
    subnet: ec2.AwaitableGetSubnetResult,
    controller_profile: iam.InstanceProfile,
    controller_security_group: ec2.SecurityGroup,
    endpoint_name: str,
    ssm_params: list[tuple[str, ssm.Parameter]],
    coredns_clusterip: str,
    backups_bucket: str,
    cluster_config: K8sControllerArgs,
    e2d_snapshot_retention_time: int,
):
    # Create the controller's ENI
    controller_eni = ec2.NetworkInterface(
        f"{get_stack()}-{cluster_config.name}-{subnet.availability_zone}",
        subnet_id=subnet.id,
        source_dest_check=False,
        security_groups=[controller_security_group] + get_default_security_groups(cls.vpc.id).ids,
        description=f"ENI for K8s Controller Cluster: {cluster_config.name}/{subnet.availability_zone}",
        tags=get_tags(service=get_stack(), role="eni", group=cluster_config.name),
        opts=ResourceOptions(parent=dependency, ignore_changes=["tagsAll", "tags"]),
    )

    # Make the launch template
    lt = ec2.LaunchTemplate(
        f"{get_stack()}-{cluster_config.name}-{subnet.availability_zone}",
        update_default_version=True,
        iam_instance_profile=ec2.LaunchTemplateIamInstanceProfileArgs(arn=controller_profile.arn),
        ebs_optimized=True,
        key_name=get_keypair(),
        block_device_mappings=[
            # Rootfs size
            ec2.LaunchTemplateBlockDeviceMappingArgs(
                device_name="/dev/xvda",
                ebs=ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                    delete_on_termination=True,
                    volume_size=cluster_config.rootfs_size_gb,
                ),
            ),
        ],
        network_interfaces=[ec2.LaunchTemplateNetworkInterfaceArgs(network_interface_id=controller_eni.id)],
        user_data=UserData(
            f"userdata-{subnet.availability_zone}",
            include_defaults=True,
            include_cloudconfig=True,
            base64_encode=False,
            replacements={
                "endpoint_name": endpoint_name,
                "cluster_name": cluster_config.name,
                # ssm parameters will be a space separated list of on-disk name and full SSM path
                # "ssm_param_paths": [Output.concat(name, " ", param.name) for name, param in ssm_params],
                # ssm parameters will be a tuple of on-disk name and full ssm path
                "ssm_params": [Output.all(name, param.name) for name, param in ssm_params],
                "service_cidr": cluster_config.service_cidr,
                "api_service_ip": ipaddress.ip_network(cluster_config.service_cidr)[1],
                "cluster_domain": cluster_config.cluster_domain,
                "cluster_dns": coredns_clusterip,
                "backups_path": f"s3://{backups_bucket}/{cluster_config.name}/",
                "dd_forward_audit_logs": str(cluster_config.dd_forward_audit_logs).lower(),
                "e2d_snapshot_retention_time": f"{e2d_snapshot_retention_time * 24}h",
                "docker_registry_cache": cluster_config.docker_registry_cache,
            },
            opts=ResourceOptions(parent=dependency),
        ).gzip_template,
        image_id=ami.id,
        instance_type=cluster_config.instance_type,
        # vpc_security_group_ids=[controller_security_group] + get_default_security_groups(vpc_id=cls.vpc.id).ids,
        tags=get_tags(get_stack(), subnet.availability_zone, cluster_config.name),
        tag_specifications=[
            ec2.LaunchTemplateTagSpecificationArgs(
                resource_type="instance",
                tags=get_tags(get_stack(), subnet.availability_zone, cluster_config.name),
            ),
            ec2.LaunchTemplateTagSpecificationArgs(
                resource_type="volume",
                tags=get_tags(get_stack(), subnet.availability_zone, cluster_config.name),
            ),
        ],
        opts=ResourceOptions(parent=controller_profile),
    )

    # Make the ASG
    controller_asg = autoscaling.Group(
        f"{get_stack()}-{cluster_config.name}-{subnet.availability_zone}",
        launch_template=autoscaling.GroupLaunchTemplateArgs(id=lt.id, version="$Latest"),
        # vpc_zone_identifiers=[subnet.id],
        availability_zones=[subnet.availability_zone],
        suspended_processes=[
            "ReplaceUnhealthy",
        ],
        health_check_type="EC2",
        health_check_grace_period=300,
        desired_capacity=1,
        max_size=1,
        min_size=0,
        tags=get_asg_tags(get_stack(), subnet.availability_zone, cluster_config.name),
        opts=ResourceOptions(parent=lt),
    )

    # We are NOT adding a lifecycle hook, yet.
    # We still need to figure a way to block multiple controllers in different ASGs from being replaced
    # at the same time.
    # autoscaling.LifecycleHook(
    #     f"{get_stack()}-{cluster_config.name}-{subnet.availability_zone}",
    #     autoscaling_group_name=controller_asg.name,
    #     default_result="ABANDON",
    #     heartbeat_timeout=900,
    #     lifecycle_transition="autoscaling:EC2_INSTANCE_LAUNCHING",
    #     opts=ResourceOptions(parent=controller_asg),
    # )

    return controller_asg, controller_eni
