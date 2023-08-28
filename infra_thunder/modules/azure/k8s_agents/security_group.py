from abc import ABC

from pulumi import ResourceOptions, ComponentResource
from pulumi_azure_native import network

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.azure.nsg import (
    generate_security_group,
    SecurityGroupIngressPeeredSupernetRule,
    SecurityGroupIngressASGRule,
)


class SecurityGroupMixin(AzureModule, ABC):
    def build_security_groups(self, parent: ComponentResource):
        asg = network.ApplicationSecurityGroup(
            "default-ag-asg",
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(parent=parent),
        )

        nsg = generate_security_group(
            name="default-ag-nsg",
            rules=[
                SecurityGroupIngressASGRule(
                    name="IntraNode",
                    description="Allow all traffic from nodes in this security group",
                    source_application_security_group_ids=[asg.id],
                    protocol=network.SecurityRuleProtocol.ASTERISK,
                    destination_all_ports=True,
                ),
                SecurityGroupIngressPeeredSupernetRule(
                    name="APIServer",
                    description="Kubernetes API requests from all supernets",
                    destination_port_ranges=["443"],
                    protocol=network.SecurityRuleProtocol.TCP,
                ),
            ],
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(parent=parent),
        )

        pod_nsg = generate_security_group(
            name="default-pods-nsg",
            rules=[
                SecurityGroupIngressPeeredSupernetRule(
                    name="Pods",
                    description="Allow all traffic from all supernets to pods",
                    destination_all_ports=True,
                    protocol=network.SecurityRuleProtocol.ASTERISK,
                )
            ],
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(parent=parent),
        )

        return asg, nsg, pod_nsg
