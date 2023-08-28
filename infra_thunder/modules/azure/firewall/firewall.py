import itertools

from pulumi import ResourceOptions
from pulumi_azure_native import network

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.azure.network import get_vnet, get_subnet
from infra_thunder.lib.azure.network.constants import SubnetPurpose
from infra_thunder.lib.config import thunder_env
from infra_thunder.lib.tags import get_tags
from .config import FirewallConfig
from .types import FirewallConnection


class Firewall(AzureModule):
    def build(self, config: FirewallConfig) -> None:
        # create azure fw service
        # create fw objects for all peered sysenvs
        # create the fw rules
        # create vnet peering
        # create routes in each vnet (no need to create reverse routes!)
        # create the ipsec gateway(?!)

        # get the list of local vnets and route tables (including their configuration)
        local_connections: dict[str, FirewallConnection] = {
            connection.sysenv: FirewallConnection(
                sysenv=connection.sysenv,
                network=network.get_virtual_network(
                    resource_group_name=connection.sysenv,
                    virtual_network_name=connection.sysenv,
                ),
                route_table=network.get_route_table(
                    resource_group_name=connection.sysenv,
                    route_table_name=connection.sysenv,
                ),
                connection=connection,
            )
            for connection in config.connections
        }

        # collect the CIDR of every sysenv, including remote sysenvs - need this for creating routes and ip groups
        # yup, we're breaking out the code golf here, folks.
        sysenv_cidrs: dict[str, str] = dict(
            {
                sysenv: connection.network.address_space.address_prefixes[0]
                for sysenv, connection in local_connections.items()
            },
            **{
                tunnel_sysenv.sysenv: tunnel_sysenv.cidr
                # get every remote connection's tunnelled sysenvs and merge the lists of lists
                for tunnel_sysenv in itertools.chain.from_iterable(
                    map(lambda x: x.tunnel_sysenvs, config.remote_connections)
                )
            },
        )

        # create an ipgroup for every sysenv
        sysenv_ipgroups: dict[str, network.IpGroup] = {
            sysenv: network.IpGroup(
                sysenv,
                ip_addresses=[cidr],
                location=self.location,
                resource_group_name=self.resourcegroup.name,
                tags=get_tags(service="transit", role="ipgroup"),
                opts=ResourceOptions(parent=self),
            )
            for sysenv, cidr in sysenv_cidrs.items()
        }

        # create the firewall policy that the Azure Firewall will reference
        policy = network.FirewallPolicy(
            "transit-fwpolicy",
            sku=network.FirewallPolicySkuArgs(tier=network.FirewallPolicySkuTier.STANDARD),
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="transit", role="fwpolicy"),
            opts=ResourceOptions(parent=self),
        )

        # create the azure firewall
        fw = network.AzureFirewall(
            "transit-firewall",
            firewall_policy=network.SubResourceArgs(
                id=policy.id,
            ),
            ip_configurations=[
                network.AzureFirewallIPConfigurationArgs(
                    subnet=network.SubResourceArgs(
                        id=get_subnet(
                            purpose=SubnetPurpose.FIREWALL,
                            resource_group_name=self.resourcegroup.name,
                        ).id
                    )
                )
            ],
            sku=network.AzureFirewallSkuArgs(
                name=network.AzureFirewallSkuName.AZF_W_V_NET,
                tier=network.AzureFirewallSkuTier.STANDARD,
            ),
            resource_group_name=self.resourcegroup.name,
            location=self.location,
            tags=get_tags(service="transit", role="firewall"),
            opts=ResourceOptions(parent=policy),
        )
        fw_ip = fw.ip_configurations[0].private_ip_address

        rules = []
        # create the list of rules for which sysenv can access which.
        for connection in config.connections:
            rules.append(
                network.AzureFirewallNetworkRuleArgs(
                    name=f"{connection.sysenv}-peered",
                    protocols=network.AzureFirewallNetworkRuleProtocol.ANY,
                    destination_ip_groups=[sysenv_ipgroups[connection.sysenv].name],
                    source_ip_groups=[
                        sysenv_ipgroups[allowed_sysenv].name for allowed_sysenv in connection.allowed_sysenvs
                    ],
                )
            )

        # create the firewall rule collection - this contains the rulecollections
        # policy -> rulecollectiongroup -> rulecollection -> rules
        network.FirewallPolicyRuleCollectionGroup(
            "transit-fwrulecollection",
            firewall_policy_name=policy.name,
            rule_collections=[
                # there is a default deny policy in the azure firewall, no need to make explicit deny rules
                network.AzureFirewallNetworkRuleCollectionArgs(
                    action=network.AzureFirewallRCActionArgs(
                        type="Allow",
                    ),
                    name="SysEnv-Peering",
                    priority=5000,
                    rules=rules,
                )
            ],
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(parent=fw),
        )

        # peer vnet to transit vnet and create routes in each vnet's route table to the fw
        for sysenv, connection in local_connections.items():
            network.VirtualNetworkPeering(
                f"{sysenv}-fwpeering",
                virtual_network_name=get_vnet(self.resourcegroup.name).name,
                remote_virtual_network=network.SubResourceArgs(
                    # id has the resource group in it, no need to specify here
                    id=connection.network.id,
                ),
                # TODO: enable remote_gateway? likely not - this will be covered by the explicit routes
                resource_group_name=self.resourcegroup.name,
                opts=ResourceOptions(parent=self),
            )

            network.Route(
                f"{sysenv}-fwroute",
                address_prefix=thunder_env.get("network_supernet"),
                next_hop_type=network.RouteNextHopType.VIRTUAL_APPLIANCE,
                next_hop_ip_address=fw_ip,
                route_table_name=connection.route_table.name,
                resource_group_name=sysenv,
                opts=ResourceOptions(parent=fw),
            )

        gateway_subnet = get_subnet(purpose=SubnetPurpose.GATEWAY, resource_group_name=self.resourcegroup.name)

        # create two public ip addresses for the vpn gateway (active-active)
        gw_primary_ip = network.PublicIPAddress(
            "transit-networkgateway-primaryip",
            public_ip_allocation_method=network.IPAllocationMethod.STATIC,
            sku=network.PublicIPAddressSkuArgs(
                name=network.PublicIPAddressSkuName.STANDARD,
                tier=network.PublicIPAddressSkuTier.REGIONAL,
            ),
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="transit", role="networkgateway"),
            opts=ResourceOptions(parent=self),
        )
        gw_secondary_ip = network.PublicIPAddress(
            "transit-networkgateway-secondaryip",
            public_ip_allocation_method=network.IPAllocationMethod.STATIC,
            sku=network.PublicIPAddressSkuArgs(
                name=network.PublicIPAddressSkuName.STANDARD,
                tier=network.PublicIPAddressSkuTier.REGIONAL,
            ),
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="transit", role="networkgateway"),
            opts=ResourceOptions(parent=self),
        )

        # create a single virtual network gateway
        gateway = network.VirtualNetworkGateway(
            "transit-networkgateway",
            active_active=True,
            vpn_gateway_generation=network.VpnGatewayGeneration.GENERATION2,
            sku=network.VirtualNetworkGatewaySkuArgs(
                name=network.VirtualNetworkGatewaySkuName.VPN_GW2,
                tier=network.VirtualNetworkGatewaySkuTier.VPN_GW2,
            ),
            vpn_type=network.VpnType.ROUTE_BASED,
            ip_configurations=[
                network.VirtualNetworkGatewayIPConfigurationArgs(
                    name="primary",
                    public_ip_address=network.SubResourceArgs(id=gw_primary_ip.id),
                    private_ip_allocation_method=network.IPAllocationMethod.DYNAMIC,
                    subnet=network.SubResourceArgs(id=gateway_subnet.id),
                ),
                network.VirtualNetworkGatewayIPConfigurationArgs(
                    name="secondary",
                    public_ip_address=network.SubResourceArgs(id=gw_secondary_ip.id),
                    private_ip_allocation_method=network.IPAllocationMethod.DYNAMIC,
                    subnet=network.SubResourceArgs(id=gateway_subnet.id),
                ),
            ],
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="transit", role="networkgateway"),
            opts=ResourceOptions(parent=self),
        )

        # create a local network gateway per ipsec peered sysenv (per ipsec peer ip address)
        # this will create 'magic' routes in the transit gw subnet to the subnets listed here,
        # which will allow connections to traverse the the vpn gw when they reach the fw
        for remote_connection in config.remote_connections:
            for ipsec_peer in remote_connection.ipsec_peers:
                peer = network.LocalNetworkGateway(
                    f"{remote_connection.name}-peer-{ipsec_peer}",
                    gateway_ip_address=ipsec_peer,
                    local_network_address_space=network.AddressSpaceArgs(
                        address_prefixes=list(map(lambda x: x.cidr, remote_connection.tunnel_sysenvs))
                    ),
                    location=self.location,
                    resource_group_name=self.resourcegroup.name,
                    tags=get_tags(
                        service="transit",
                        role="localgateway",
                        group=remote_connection.name,
                    ),
                    opts=ResourceOptions(parent=gateway),
                )
                # the connection ties everything together
                connection = network.VirtualNetworkGatewayConnection(
                    f"{remote_connection.name}-connection-{ipsec_peer}",
                    virtual_network_gateway1=None,
                )
