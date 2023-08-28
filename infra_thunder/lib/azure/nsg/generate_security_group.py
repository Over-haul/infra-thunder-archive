from typing import Optional

from pulumi import ResourceOptions
from pulumi_azure_native import network

from infra_thunder.lib.azure.resources import get_resourcegroup
from .types import SecurityGroupIngressRuleBase, SecurityGroupIngressLocalSupernetRule


def generate_security_group(
    name: str,
    rules: list[SecurityGroupIngressRuleBase],
    resource_group_name: Optional[str] = None,
    disable_default_rules: Optional[bool] = None,
    opts: Optional[ResourceOptions] = None,
) -> network.NetworkSecurityGroup:
    # avoid call to get_resourcegroup if resource_group_name is set
    resource_group_name_ = resource_group_name or get_resourcegroup().name

    sg_rules = [rule.to_rule(idx * 10 + 200) for idx, rule in enumerate(rules)]

    # Default rules here
    default_rules = [
        # add an internal SSH rule to allow bastion access
        # TODO: allow this to be disabled independently of other rules, or allow scoping to just the vpn prefix(?)
        SecurityGroupIngressLocalSupernetRule(
            name="AllowSSH",
            description="Allow SSH access from any machine inside this VNET",
            protocol=network.SecurityRuleProtocol.TCP,
            destination_port_ranges=["22"],
        ).to_rule(priority=3000),
        # add an internal ping rule to allow health checks
        SecurityGroupIngressLocalSupernetRule(
            name="Default-Ping",
            description="Allow ping access from any machine inside this VNET",
            protocol=network.SecurityRuleProtocol.ICMP,
            destination_all_ports=True,
        ).to_rule(priority=3010),
        # add the last default deny rule to enforce other rules
        network.SecurityRuleArgs(
            priority=4000,
            name="Last-Rule-Deny",
            description="Last rule in the chain. This prevents unintentional access via the AllowVnetInBound "
            "and AllowAzureLoadBalancerInBound default rules.",
            access=network.SecurityRuleAccess.DENY,
            direction=network.SecurityRuleDirection.INBOUND,
            protocol=network.SecurityRuleProtocol.ASTERISK,
            source_address_prefix="*",
            source_port_range="*",
            destination_address_prefix="*",
            destination_port_range="*",
        ),
    ]

    return network.NetworkSecurityGroup(
        name,
        security_rules=sg_rules + default_rules if not disable_default_rules else sg_rules,
        resource_group_name=resource_group_name_,
        opts=opts,
    )
