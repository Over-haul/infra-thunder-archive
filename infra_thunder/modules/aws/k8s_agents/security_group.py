from pulumi import ResourceOptions, get_stack

from infra_thunder.lib.security_groups import (
    generate_security_group,
    SecurityGroupIngressRule,
)


def create_nodegroup_securitygroup(dependency, cluster_name: str):
    return generate_security_group(
        name=f"{get_stack()}-{cluster_name}",
        ingress_rules=[
            SecurityGroupIngressRule(
                description="Allow all traffic from nodes in this security group",
                from_port=0,
                to_port=0,
                protocol="-1",
                self=True,
            ),
            SecurityGroupIngressRule(
                description="Allow HTTP load balancer traffic",
                from_port=8080,
                to_port=8080,
                protocol="tcp",
                allow_vpc_supernet=True,
            ),
            SecurityGroupIngressRule(
                description="Allow HTTPS load balancer traffic",
                from_port=8443,
                to_port=8443,
                protocol="tcp",
                allow_vpc_supernet=True,
            ),
            SecurityGroupIngressRule(
                description="Allow traefik management traffic",
                from_port=9000,
                to_port=9000,
                protocol="tcp",
                allow_vpc_supernet=True,
            ),
            SecurityGroupIngressRule(
                description="Allow kubelet endpoint",
                from_port=10250,
                to_port=10250,
                protocol="tcp",
                allow_vpc_supernet=True,
            ),
            SecurityGroupIngressRule(
                description="Allow GENEVE routing",
                from_port=6081,
                to_port=6081,
                protocol="udp",
                allow_vpc_supernet=True,
            ),
            SecurityGroupIngressRule(
                description="Allow TCP DNS requests",
                from_port=53,
                to_port=53,
                protocol="tcp",
                allow_vpc_supernet=True,
            ),
            SecurityGroupIngressRule(
                description="Allow UDP DNS requests",
                from_port=53,
                to_port=53,
                protocol="udp",
                allow_vpc_supernet=True,
            ),
            SecurityGroupIngressRule(
                description="Allow TCP traffic to NodePort services",
                from_port=30000,
                to_port=32767,
                protocol="tcp",
                allow_vpc_supernet=True,
                allow_peered_supernets=True,
            ),
            SecurityGroupIngressRule(
                description="Allow UDP traffic to NodePort services",
                from_port=30000,
                to_port=32767,
                protocol="udp",
                allow_vpc_supernet=True,
                allow_peered_supernets=True,
            ),
        ],
        opts=ResourceOptions(parent=dependency),
    )
