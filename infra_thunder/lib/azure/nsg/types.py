from abc import abstractmethod
from dataclasses import dataclass
from functools import partial
from typing import Optional, Union

from pulumi import Output
from pulumi_azure_native.network import (
    SecurityRuleProtocol,
    SecurityRuleArgs,
    SecurityRuleAccess,
    SecurityRuleDirection,
    ApplicationSecurityGroupArgs,
)

from infra_thunder.lib.config import thunder_env


@dataclass
class SecurityGroupIngressRuleBase:
    name: str
    """Name of the rule"""

    protocol: SecurityRuleProtocol
    """Protocol for this rule"""

    description: Optional[str] = None
    """(Optional) Rule description"""

    destination_port_ranges: Optional[list[str]] = None
    """Destination port ranges"""

    destination_all_ports: Optional[bool] = False
    """Allow all ports on the destination"""

    @abstractmethod
    def to_rule(self, priority: int) -> SecurityRuleArgs:
        pass

    def __post_init__(self):
        if self.destination_all_ports and self.destination_port_ranges:
            raise Exception("Cannot mix all ports and port ranges")

        self._partial_security_rule_args: partial[SecurityRuleArgs] = partial(
            SecurityRuleArgs,
            access=SecurityRuleAccess.ALLOW,
            direction=SecurityRuleDirection.INBOUND,
            protocol=self.protocol,
            description=self.description,
            source_port_range="*",
            destination_address_prefix="*",  # SG rules apply to a specific network interface, no need to specify dest
            destination_port_ranges=self.destination_port_ranges,
            destination_port_range="*" if self.destination_all_ports else None,
        )


@dataclass
class SecurityGroupIngressASGRule(SecurityGroupIngressRuleBase):
    source_application_security_group_ids: list[Union[str, Output[str]]] = None
    """Allow access from the listed application security groups"""

    def to_rule(self, priority: int):
        return self._partial_security_rule_args(
            priority=priority,  # user defined rules start at 200
            name=f"ASG-{self.name}",
            source_application_security_groups=[
                ApplicationSecurityGroupArgs(
                    id=asg_id,
                )
                for asg_id in self.source_application_security_group_ids
            ],
        )


@dataclass
class SecurityGroupIngressCustomRule(SecurityGroupIngressRuleBase):
    source_address_prefixes: list[str] = None
    """Source IP CIDRs"""

    def to_rule(self, priority: int):
        return self._partial_security_rule_args(
            priority=priority,
            name=f"Custom-{self.name}",
            source_address_prefixes=self.source_address_prefixes,
        )


@dataclass
class SecurityGroupIngressInternetRule(SecurityGroupIngressRuleBase):
    def to_rule(self, priority: int):
        return self._partial_security_rule_args(
            priority=priority,
            name=f"Internet-{self.name}",
            source_address_prefix="*",
        )


@dataclass
class SecurityGroupIngressLocalSupernetRule(SecurityGroupIngressRuleBase):
    def to_rule(self, priority: int):
        return self._partial_security_rule_args(
            priority=priority,
            name=f"LocalSupernet-{self.name}",
            source_address_prefix="VirtualNetwork",
        )


@dataclass
class SecurityGroupIngressPeeredSupernetRule(SecurityGroupIngressRuleBase):
    def to_rule(self, priority: int):
        return self._partial_security_rule_args(
            priority=priority,
            name=f"PeeredSupernets-{self.name}",
            source_address_prefix=thunder_env.get("network_supernet"),
        )


@dataclass
class SecurityGroupIngressLBHealthRule(SecurityGroupIngressRuleBase):
    def to_rule(self, priority: int):
        return self._partial_security_rule_args(
            priority=priority,
            name=f"LoadBalancerHealth-{self.name}",
            source_address_prefix="AzureLoadBalancer",
        )
