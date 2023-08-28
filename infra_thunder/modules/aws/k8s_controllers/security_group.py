from pulumi import ResourceOptions, ComponentResource, get_stack
from pulumi_aws import ec2

from infra_thunder.lib.security_groups import generate_security_group
from infra_thunder.lib.security_groups.types import SecurityGroupIngressRule
from .config import K8sControllerArgs


def create_controller_security_group(
    cls, dependency: ComponentResource, cluster_config: K8sControllerArgs
) -> ec2.SecurityGroup:
    """
    Create the security group for the controllers
    This security group controls node -> controller communications

    TODO: Could implement source SG mapping here
    (make the cluster SG before this and add it to the inbound on this rule)

    :param cluster_config:
    :return:
    """

    rules = [
        SecurityGroupIngressRule(
            description="Allow all traffic from nodes in this security group",
            from_port=0,
            to_port=0,
            protocol="-1",
            self=True,
        ),
        SecurityGroupIngressRule(
            description="in-VPC kubernetes API requests",
            from_port=443,
            to_port=443,
            protocol="tcp",
            allow_vpc_supernet=True,
            allow_peered_supernets=True,
        ),
    ]

    if cluster_config.enable_clusterip_routes:
        rules.append(
            SecurityGroupIngressRule(
                description="Allow all traffic to cluster IP services",
                from_port=0,
                to_port=0,
                protocol="-1",
                allow_vpc_supernet=True,
                allow_peered_supernets=True,
            )
        )

    # NOTE: no egress security group is necessary since egress anywhere is covered by the default security group
    return generate_security_group(
        name=f"{get_stack()}-{cluster_config.name}",
        ingress_rules=rules,
        opts=ResourceOptions(parent=dependency),
    )


def create_pod_security_group(
    cls, dependency: ComponentResource, cluster_config: K8sControllerArgs
) -> ec2.SecurityGroup:
    """
    Create the security group for pods

    :param cluster_config:
    :return:
    """
    return generate_security_group(
        name=f"k8s-node-{cluster_config.name}-pods",
        ingress_rules=[
            SecurityGroupIngressRule(
                description="Allow all traffic from VPC supernet to pods",
                from_port=0,
                to_port=0,
                protocol="-1",
                allow_vpc_supernet=True,
                allow_peered_supernets=True,
            )
        ],
        opts=ResourceOptions(parent=dependency),
    )
