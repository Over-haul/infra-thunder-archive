from ..config import (
    tag_prefix,
    team,
    get_sysenv,
    get_stack,
    get_project,
    get_purpose,
    get_phase,
)


def get_tags(service, role, group=None) -> dict:
    """
    Generate tag dict for resources

    example tags:
      k8s controllers:
        Name = kubernetes-controller
               service-role
        thunder:sysenv = co-aws-us-west-2-prod-app
        thunder:service = kubernetes
        thunder:role = controller
        thunder:group = main
        thunder:createdby = terraform
        thunder:team = infrastructure
        thunder:project = kubernetes-controllers
        thunder:stack = co-aws-us-west-2-prod-app
        thunder:purpose = app
        thunder:phase = prod
        - ideally: oh:stack = aws/kubernetes/controllers

      cassandra-app servers:
        Name = cassandra-app
               service-group
        thunder:sysenv = co-aws-us-west-2-prod-app
        thunder:service = cassandra
        thunder:role = instance
        thunder:group = app
        thunder:createdby = pulumi
        thunder:team = infrastructure
        thunder:project = cassandra
        thunder:stack = co-aws-us-west-2-prod-app
        thunder:purpose = app
        thunder:phase = prod

      jenkins-agent servers:
        Name = jenkins-agent
               service-role
        thunder:sysenv = co-aws-us-west-2-prod-app
        thunder:service = jenkins
        thunder:role = agent
        thunder:group = main
        thunder:createdby = pulumi
        thunder:team = infrastructure
        thunder:project = jenkins-agent
        thunder:stack = co-aws-us-west-2-prod-app
        thunder:purpose = app
        thunder:phase = prod

      jenkins-agent-integrations servers:
        Name = jenkins-agent
               service-role
        thunder:sysenv = co-aws-us-west-2-prod-app
        thunder:service = jenkins
        thunder:role = agent
        thunder:group = integrations
        thunder:createdby = pulumi
        thunder:team = infrastructure
        thunder:project = jenkins-agent
        thunder:stack = co-aws-us-west-2-prod-app
        thunder:purpose = app
        thunder:phase = prod

      subnet-public-us-west-2a subnet:
        Name = subnet-public
               service-role
        thunder:sysenv = co-aws-us-west-2-prod-app
        thunder:service = subnet
        thunder:role = public
        thunder:group = us-west-2a
        thunder:createdby = pulumi
        thunder:team = infrastructure
        thunder:project = vpc
        thunder:stack = co-aws-us-west-2-prod-app
        thunder:purpose = app
        thunder:phase = prod

      natgateway-main-us-west-2a:
        Name = natgateway-main
               service-role
        thunder:sysenv = co-aws-us-west-2-prod-app
        thunder:service = natgateway
        thunder:role = main
        thunder:group = us-west-2a
        thunder:createdby = pulumi
        thunder:team = infrastructure
        thunder:project = vpc
        thunder:stack = co-aws-us-west-2-prod-app
        thunder:purpose = app
        thunder:phase = prod

      vpc-co-aws-us-west-2-prod-app vpc:
        Name = vpc-co-aws-us-west-2-prod-app
               service-role
        thunder:sysenv = co-aws-us-west-2-prod-app
        thunder:service = vpc
        thunder:role = co-aws-us-west-2-prod-app
        thunder:group = us-west-2
        thunder:createdby = pulumi
        thunder:team = infrastructure
        thunder:project = vpc
        thunder:stack = co-aws-us-west-2-prod-app
        thunder:purpose = app
        thunder:phase = prod

    :param service: This resource's "namespace" (kubernetes, cassandra, subnet,...)
    :param role: The role this resource performs within the namespace (master, instance, public,...)
    :param group: The group this resource belongs to (integrations, us-west-2a). Leave unset to use "main".
    :return: Dict of tags
    """

    group_name = "main" if not group else group
    group_suffix = f"-{group}" if group else ""
    sysenv = get_sysenv()

    return {
        "Name": f"{service}-{role}{group_suffix}",
        f"{tag_prefix}sysenv": sysenv,
        f"{tag_prefix}service": service,
        f"{tag_prefix}role": role,
        f"{tag_prefix}group": group_name,
        f"{tag_prefix}team": team,
        f"{tag_prefix}createdby": "pulumi",
        f"{tag_prefix}stack": get_stack(),
        f"{tag_prefix}project": get_project(),
        f"{tag_prefix}purpose": get_purpose(),
        f"{tag_prefix}phase": get_phase(),
    }


def get_asg_tags(service, role, group=None, propagate_at_launch=False) -> list[dict]:
    """
    Generate tag dict for resources
    :param service: This resource's "namespace" (kubernetes, cassandra, subnet,...)
    :param role: The role this resource performs within the namespace (master, instance, public,...)
    :param group: The group this resource belongs to (integrations, us-west-2a). Leave unset to use "main".
    :return: List of dicts of tags
    """
    return [
        {"key": k, "value": v, "propagate_at_launch": propagate_at_launch}
        for k, v in get_tags(service, role, group).items()
    ]
