from typing import Optional

from pulumi import ResourceOptions
from pulumi.output import Input
from pulumi_aws import ec2

from infra_thunder.lib.vpc import get_prefix_list, get_peered_prefix_list
from .types import SecurityGroupIngressRule


def generate_security_group_ingress_rules(
    rules: list[SecurityGroupIngressRule],
    security_group_id: Input[str],
    name: str,
    opts: Optional[ResourceOptions] = None,
) -> list[ec2.SecurityGroupRule]:
    def generate_rule(index: int, rule: SecurityGroupIngressRule) -> ec2.SecurityGroupRule:
        prefix_lists = [] if rule.allow_vpc_supernet or rule.allow_peered_supernets else None
        if rule.allow_vpc_supernet:
            prefix_lists.append(get_prefix_list().id)
        if rule.allow_peered_supernets:
            prefix_lists.append(get_peered_prefix_list().id)

        return ec2.SecurityGroupRule(
            f"{name}-{index}",
            type="ingress",
            description=rule.description,
            from_port=rule.from_port,
            to_port=rule.to_port,
            protocol=rule.protocol,
            security_group_id=security_group_id,
            cidr_blocks=rule.cidr_blocks,
            self=rule.self,
            source_security_group_id=rule.source_security_group_id,
            prefix_list_ids=prefix_lists,
            opts=opts,
        )

    return [generate_rule(index, rule) for index, rule in enumerate(rules)]
