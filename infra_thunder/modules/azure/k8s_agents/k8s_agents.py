from functools import partial

from pulumi import ComponentResource, ResourceOptions

from infra_thunder.lib.config import get_sysenv
from infra_thunder.lib.kubernetes import get_cluster
from .config import K8sAgentsConfig, K8sAgentsExports
from .gateway import GatewayMixin
from .node_group import NodeGroupMixin
from .security_group import SecurityGroupMixin


class K8sAgents(GatewayMixin, SecurityGroupMixin, NodeGroupMixin):
    def build(self, config: K8sAgentsConfig) -> K8sAgentsExports:
        cluster_name = get_sysenv()

        # Create component resource to group things together
        cluster_component = ComponentResource(
            t=f"pkg:thunder:{self.provider}:{self.__class__.__name__.lower()}:cluster:{cluster_name}",
            name=get_sysenv(),
            props=None,
            opts=ResourceOptions(parent=self),
        )

        # Get K8s control plane we're creating agents for
        controller_config = get_cluster(cluster_name)

        # gateways
        gateway_identity_name = self.create_gateway_identity(config.gateway, config.extra_gateways, cluster_component)
        build_gateway = partial(
            self.build_gateway,
            identity_name=gateway_identity_name,
            parent=cluster_component,
        )
        default_gateway = build_gateway(name="default", ssl_config=config.gateway.ssl_config)
        extra_gateways = [build_gateway(name=g.name, ssl_config=g.ssl_config) for g in config.extra_gateways]

        # security groups
        asg, nsg, pod_nsg = self.build_security_groups(cluster_component)

        # node groups/vmss
        for node_group_config in config.node_groups:
            self.build_node_group(
                config=node_group_config,
                default_gateway=default_gateway,
                extra_gateways=extra_gateways,
                asg=asg,
                nsg=nsg,
                pod_nsg=pod_nsg,
                parent=cluster_component,
            )

        return K8sAgentsExports(
            node_groups=[n.name for n in config.node_groups],
            gateway=default_gateway,
            extra_gateways=extra_gateways,
        )
