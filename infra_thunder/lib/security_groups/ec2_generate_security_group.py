from typing import Optional

from pulumi import ResourceOptions
from pulumi_aws import ec2

from .types import SecurityGroupIngressRule
from ..config import get_stack, get_sysenv
from ..tags import get_tags
from ..vpc import get_vpc, get_prefix_list, get_peered_prefix_list


def generate_security_group(
    ingress_rules: list[SecurityGroupIngressRule],
    name: str,
    *,
    opts: Optional[ResourceOptions] = None,
    vpc_id: Optional[str] = None,
) -> ec2.SecurityGroup:
    rules = []
    for rule in ingress_rules:
        prefix_lists = [] if rule.allow_vpc_supernet or rule.allow_peered_supernets else None
        if rule.allow_vpc_supernet:
            prefix_lists.append(get_prefix_list().id)
        if rule.allow_peered_supernets:
            prefix_lists.append(get_peered_prefix_list().id)

        rules.append(
            ec2.SecurityGroupIngressArgs(
                description=rule.description,
                from_port=rule.from_port,
                to_port=rule.to_port,
                protocol=rule.protocol,
                cidr_blocks=rule.cidr_blocks,
                prefix_list_ids=prefix_lists,
                self=rule.self,
            )
        )
    return ec2.SecurityGroup(
        name,
        ingress=rules,
        description=f"Security Group for {get_stack()} {get_sysenv()}",
        vpc_id=vpc_id or get_vpc().id,
        tags=get_tags(get_stack(), "sg", name),
        opts=opts,
    )
