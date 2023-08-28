from pulumi import ResourceOptions, ComponentResource, get_stack
from pulumi_azure_native import network

from infra_thunder.lib.tags import get_tags


def create_lb(
    cls, dependency: ComponentResource, subnet: network.AwaitableGetSubnetResult
) -> (network.LoadBalancer, str):
    # create lb
    lb_name = get_stack()
    pool_name = "controller-pool"
    frontend_name = f"{lb_name}-frontend"
    apiserver_probe_name = f"{lb_name}-apiserver-livez"
    etcd_probe_name = f"{lb_name}-etcd-livez"

    lb = network.LoadBalancer(
        lb_name,
        load_balancer_name=lb_name,
        sku=network.LoadBalancerSkuArgs(
            name=network.LoadBalancerSkuName.STANDARD,
            tier=network.LoadBalancerSkuTier.REGIONAL,
        ),
        frontend_ip_configurations=[
            network.FrontendIPConfigurationArgs(
                name=frontend_name,
                private_ip_allocation_method=network.IPAllocationMethod.DYNAMIC,
                private_ip_address_version="IPv4",  # I_Pv4 wut
                subnet=network.SubnetArgs(id=subnet.id),
            ),
        ],
        backend_address_pools=[network.BackendAddressPoolArgs(name=pool_name)],
        probes=[
            network.ProbeArgs(
                name=apiserver_probe_name,
                protocol=network.ProtocolType.TCP,
                port=443,
                interval_in_seconds=5,
                number_of_probes=2,
            ),
            network.ProbeArgs(
                name=etcd_probe_name,
                protocol=network.ProtocolType.TCP,
                port=2379,
                interval_in_seconds=5,
                number_of_probes=2,
            ),
        ],
        load_balancing_rules=[
            network.LoadBalancingRuleArgs(
                name="k8s-apiserver-443",
                frontend_ip_configuration=network.SubResourceArgs(
                    id=cls.build_resource_id(
                        resource_provider_namespace="Microsoft.Network",
                        parent_resource_type="loadBalancers",
                        parent_resource_name=lb_name,
                        resource_type="frontendIPConfigurations",
                        resource_name=frontend_name,
                    ),
                ),
                frontend_port=443,
                backend_port=443,
                enable_floating_ip=False,
                idle_timeout_in_minutes=30,
                protocol=network.ProtocolType.TCP,
                load_distribution=network.LoadDistribution.DEFAULT,
                probe=network.SubResourceArgs(
                    id=cls.build_resource_id(
                        resource_provider_namespace="Microsoft.Network",
                        parent_resource_type="loadBalancers",
                        parent_resource_name=lb_name,
                        resource_type="probes",
                        resource_name=apiserver_probe_name,
                    ),
                ),
                disable_outbound_snat=True,
                enable_tcp_reset=False,
                backend_address_pool=network.SubResourceArgs(
                    id=cls.build_resource_id(
                        resource_provider_namespace="Microsoft.Network",
                        parent_resource_type="loadBalancers",
                        parent_resource_name=lb_name,
                        resource_type="backendAddressPools",
                        resource_name=pool_name,
                    )
                ),
            ),
            network.LoadBalancingRuleArgs(
                name="k8s-etcd-2379",
                frontend_ip_configuration=network.SubResourceArgs(
                    id=cls.build_resource_id(
                        resource_provider_namespace="Microsoft.Network",
                        parent_resource_type="loadBalancers",
                        parent_resource_name=lb_name,
                        resource_type="frontendIPConfigurations",
                        resource_name=frontend_name,
                    ),
                ),
                frontend_port=2379,
                backend_port=2379,
                enable_floating_ip=False,
                idle_timeout_in_minutes=30,
                protocol=network.ProtocolType.TCP,
                load_distribution=network.LoadDistribution.DEFAULT,
                probe=network.SubResourceArgs(
                    id=cls.build_resource_id(
                        resource_provider_namespace="Microsoft.Network",
                        parent_resource_type="loadBalancers",
                        parent_resource_name=lb_name,
                        resource_type="probes",
                        resource_name=etcd_probe_name,
                    ),
                ),
                disable_outbound_snat=True,
                enable_tcp_reset=False,
                backend_address_pool=network.SubResourceArgs(
                    id=cls.build_resource_id(
                        resource_provider_namespace="Microsoft.Network",
                        parent_resource_type="loadBalancers",
                        parent_resource_name=lb_name,
                        resource_type="backendAddressPools",
                        resource_name=pool_name,
                    )
                ),
            ),
        ],
        tags=get_tags(service=get_stack(), role="loadbalancer"),
        **cls.common_args,
        opts=ResourceOptions(parent=dependency),
    )

    pool = cls.build_resource_id(
        resource_provider_namespace="Microsoft.Network",
        parent_resource_type="loadBalancers",
        parent_resource_name=lb_name,
        resource_type="backendAddressPools",
        resource_name=pool_name,
    )

    return lb, pool
