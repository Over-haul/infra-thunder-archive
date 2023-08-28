from pulumi import ResourceOptions, ComponentResource
from pulumi_azure_native import network

from infra_thunder.lib.azure.nsg import (
    generate_security_group,
    SecurityGroupIngressLocalSupernetRule,
    SecurityGroupIngressPeeredSupernetRule,
    SecurityGroupIngressASGRule,
    SecurityGroupIngressLBHealthRule,
)


def create_controller_asg_and_nsg(
    cls, dependency: ComponentResource
) -> tuple[network.ApplicationSecurityGroup, network.NetworkSecurityGroup]:
    # Create the application security group that all controllers use (to allow 'self' communication
    asg = network.ApplicationSecurityGroup(
        "controller-asg",
        location=cls.location,
        resource_group_name=cls.resourcegroup.name,
        opts=ResourceOptions(parent=dependency),
    )

    rules = [
        SecurityGroupIngressASGRule(
            name="IntraNode",
            description="Allow all traffic from nodes in this security group",
            source_application_security_group_ids=[asg.id],
            protocol=network.SecurityRuleProtocol.ASTERISK,
            destination_all_ports=True,
        ),
        SecurityGroupIngressLBHealthRule(
            name="APIServerEtcd",
            description="Allow Azure LB to health check APIServer and etcd",
            protocol=network.SecurityRuleProtocol.TCP,
            destination_port_ranges=["443", "2379"],
        ),
        SecurityGroupIngressPeeredSupernetRule(
            name="APIServer",
            description="Kubernetes API requests from all supernets",
            destination_port_ranges=["443"],
            protocol=network.SecurityRuleProtocol.TCP,
        ),
        SecurityGroupIngressLocalSupernetRule(
            name="Kubelet",
            description="Local supernet access to kubelet endpoints",
            destination_port_ranges=["10250"],
            protocol=network.SecurityRuleProtocol.TCP,
        ),
        SecurityGroupIngressPeeredSupernetRule(
            name="NodePortsTCP",
            description="Kubernetes NodePort TCP Services",
            destination_port_ranges=["30000-32767"],
            protocol=network.SecurityRuleProtocol.TCP,
        ),
        SecurityGroupIngressPeeredSupernetRule(
            name="NodePortsUDP",
            description="Kubernetes NodePort UDP Services",
            destination_port_ranges=["30000-32767"],
            protocol=network.SecurityRuleProtocol.UDP,
        ),
    ]

    nsg = generate_security_group(
        name="controller-nsg",
        rules=rules,
        resource_group_name=cls.resourcegroup.name,
        opts=ResourceOptions(parent=dependency),
    )

    return asg, nsg


def create_pod_nsg(cls, dependency: ComponentResource) -> network.NetworkSecurityGroup:
    return generate_security_group(
        name="pods-nsg",
        rules=[
            SecurityGroupIngressPeeredSupernetRule(
                name="Pods",
                description="Allow all traffic from all supernets to pods",
                destination_all_ports=True,
                protocol=network.SecurityRuleProtocol.ASTERISK,
            )
        ],
        resource_group_name=cls.resourcegroup.name,
        opts=ResourceOptions(parent=dependency),
    )
