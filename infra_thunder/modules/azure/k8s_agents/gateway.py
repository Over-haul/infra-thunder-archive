from abc import ABC
from functools import cache

from pulumi import ComponentResource, get_stack, ResourceOptions
from pulumi_azure_native import network, keyvault, managedidentity, authorization

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.azure.iam import get_role_definition_id
from infra_thunder.lib.azure.network import get_subnet, SubnetPurpose
from infra_thunder.lib.config import get_sysenv
from infra_thunder.lib.tags import get_tags
from .config import GatewayExports, SSLConfig, SysenvGatewayConfig, GatewayConfig


class GatewayMixin(AzureModule, ABC):
    def create_gateway_identity(
        self,
        default_gateway: SysenvGatewayConfig,
        extra_gateways: list[GatewayConfig],
        parent: ComponentResource,
    ) -> str:
        name = f"{get_sysenv()}-{self.__class__.__name__.lower()}-gateway"

        identity = managedidentity.UserAssignedIdentity(
            name,
            resource_name_=name,
            **self.common_args,
            tags=get_tags(service=get_stack(), role="identity", group=name),
            opts=ResourceOptions(parent=parent),
        )

        @cache
        def create_gateway_identity_role_assignment(resource_group: str, vault_name: str):
            vault = keyvault.get_vault(resource_group_name=resource_group, vault_name=vault_name)

            if not vault.properties.enable_rbac_authorization:
                raise Exception(
                    f"vault `{vault_name}` in `{resource_group}` must have rbac authorization enabled to get ssl certificate"
                )

            return authorization.RoleAssignment(
                f"{name}-{vault_name}-assignment",
                scope=vault.id,
                principal_id=identity.principal_id,
                principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
                role_definition_id=get_role_definition_id("Key Vault Secrets User", scope=vault.id),
                opts=ResourceOptions(parent=identity),
            )

        for ssl_config in (
            default_gateway.ssl_config,
            *[g.ssl_config for g in extra_gateways],
        ):
            create_gateway_identity_role_assignment(ssl_config.key_vault_resource_group, ssl_config.key_vault_name)

        return name

    def build_gateway(
        self,
        name: str,
        ssl_config: SSLConfig,
        identity_name: str,
        parent: ComponentResource,
    ) -> GatewayExports:
        frontend_ip = network.PublicIPAddress(
            name,
            public_ip_allocation_method=network.IPAllocationMethod.STATIC,
            sku=network.PublicIPAddressSkuArgs(
                name=network.PublicIPAddressSkuName.STANDARD,
                tier=network.PublicIPAddressSkuTier.REGIONAL,
            ),
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service=get_stack(), role="publicip", group=name),
            opts=ResourceOptions(parent=parent),
        )

        frontend_port = network.ApplicationGatewayFrontendPortArgs(
            name=f"{name}-80",
            port=80,
        )

        ssl_port = network.ApplicationGatewayFrontendPortArgs(
            name=f"{name}-443",
            port=443,
        )

        http_setting = network.ApplicationGatewayBackendHttpSettingsArgs(
            name=f"{name}-be-http-settings",
            port=80,
            protocol=network.ApplicationGatewayProtocol.HTTP,
            cookie_based_affinity=network.ApplicationGatewayCookieBasedAffinity.DISABLED,
            request_timeout=20,
        )

        load_balancer_subnet = get_subnet(
            purpose=SubnetPurpose.LOAD_BALANCER,
            resource_group_name=self.resourcegroup.name,
        )

        bap_name = f"{name}-bap"

        network.ApplicationGateway(
            f"{name}-app-gw",
            application_gateway_name=name,
            enable_http2=False,
            sku=network.ApplicationGatewaySkuArgs(
                capacity=1,
                name=network.ApplicationGatewaySkuName.STANDARD_V2,
                tier=network.ApplicationGatewayTier.STANDARD_V2,
            ),
            gateway_ip_configurations=[
                network.ApplicationGatewayIPConfigurationArgs(
                    name=name,
                    subnet=network.SubResourceArgs(
                        id=load_balancer_subnet.id,
                    ),
                ),
            ],
            frontend_ip_configurations=[
                network.ApplicationGatewayFrontendIPConfigurationArgs(
                    name=f"{name}-fe-ip-conf",
                    public_ip_address=network.SubResourceArgs(
                        id=frontend_ip.id,
                    ),
                )
            ],
            frontend_ports=[
                frontend_port,
                ssl_port,
            ],
            backend_address_pools=[
                network.ApplicationGatewayBackendAddressPoolArgs(
                    name=bap_name,
                    backend_addresses=[network.ApplicationGatewayBackendAddressArgs(fqdn=name, ip_address=None)],
                ),
            ],
            backend_http_settings_collection=[
                http_setting,
            ],
            ssl_certificates=[
                network.ApplicationGatewaySslCertificateArgs(
                    name=f"{name}-ssl-cert",
                    key_vault_secret_id=keyvault.get_secret(
                        resource_group_name=ssl_config.key_vault_resource_group,
                        vault_name=ssl_config.key_vault_name,
                        secret_name=ssl_config.key_vault_secret_name,
                    ).properties.secret_uri_with_version,
                )
            ],
            ssl_profiles=[
                network.ApplicationGatewaySslProfileArgs(
                    name=f"{name}-ssl-profile",
                    ssl_policy=network.ApplicationGatewaySslPolicyArgs(
                        min_protocol_version=network.ApplicationGatewaySslProtocol.TL_SV1_2,
                        policy_type=network.ApplicationGatewaySslPolicyType.CUSTOM,
                        cipher_suites=[
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_RS_A_WIT_H_AE_S_256_CB_C_SHA384,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_RS_A_WIT_H_AE_S_128_CB_C_SHA256,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_RS_A_WIT_H_AE_S_256_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_RS_A_WIT_H_AE_S_128_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_DH_E_RS_A_WIT_H_AE_S_256_GC_M_SHA384,
                            network.ApplicationGatewaySslCipherSuite.TL_S_DH_E_RS_A_WIT_H_AE_S_128_GC_M_SHA256,
                            network.ApplicationGatewaySslCipherSuite.TL_S_DH_E_RS_A_WIT_H_AE_S_256_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_DH_E_RS_A_WIT_H_AE_S_128_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_RS_A_WIT_H_AE_S_256_GC_M_SHA384,
                            network.ApplicationGatewaySslCipherSuite.TL_S_RS_A_WIT_H_AE_S_128_GC_M_SHA256,
                            network.ApplicationGatewaySslCipherSuite.TL_S_RS_A_WIT_H_AE_S_256_CB_C_SHA256,
                            network.ApplicationGatewaySslCipherSuite.TL_S_RS_A_WIT_H_AE_S_128_CB_C_SHA256,
                            network.ApplicationGatewaySslCipherSuite.TL_S_RS_A_WIT_H_AE_S_256_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_RS_A_WIT_H_AE_S_128_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_ECDS_A_WIT_H_AE_S_256_GC_M_SHA384,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_ECDS_A_WIT_H_AE_S_128_GC_M_SHA256,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_ECDS_A_WIT_H_AE_S_256_CB_C_SHA384,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_ECDS_A_WIT_H_AE_S_128_CB_C_SHA256,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_ECDS_A_WIT_H_AE_S_256_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_ECDS_A_WIT_H_AE_S_128_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_DH_E_DS_S_WIT_H_AE_S_256_CB_C_SHA256,
                            network.ApplicationGatewaySslCipherSuite.TL_S_DH_E_DS_S_WIT_H_AE_S_128_CB_C_SHA256,
                            network.ApplicationGatewaySslCipherSuite.TL_S_DH_E_DS_S_WIT_H_AE_S_256_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_DH_E_DS_S_WIT_H_AE_S_128_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_RS_A_WIT_H_3_DE_S_ED_E_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_DH_E_DS_S_WIT_H_3_DE_S_ED_E_CB_C_SHA,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_RS_A_WIT_H_AE_S_128_GC_M_SHA256,
                            network.ApplicationGatewaySslCipherSuite.TL_S_ECDH_E_RS_A_WIT_H_AE_S_256_GC_M_SHA384,
                        ],
                    ),
                )
            ],
            identity=network.ManagedServiceIdentityArgs(
                type="UserAssigned",
                user_assigned_identities={
                    self.build_resource_id(
                        resource_provider_namespace="Microsoft.ManagedIdentity",
                        parent_resource_type="userAssignedIdentities",
                        parent_resource_name=identity_name,
                    ): {}
                },
            ),
            http_listeners=[
                network.ApplicationGatewayHttpListenerArgs(
                    name=f"{name}-ssl",
                    frontend_ip_configuration=network.SubResourceArgs(
                        id=self.build_resource_id(
                            resource_provider_namespace="Microsoft.Network",
                            parent_resource_type="applicationGateways",
                            parent_resource_name=name,
                            resource_type="frontendIpConfigurations",
                            resource_name=f"{name}-fe-ip-conf",
                        ),
                    ),
                    frontend_port=network.SubResourceArgs(
                        id=self.build_resource_id(
                            resource_provider_namespace="Microsoft.Network",
                            parent_resource_type="applicationGateways",
                            parent_resource_name=name,
                            resource_type="frontendPorts",
                            resource_name=f"{name}-443",
                        ),
                    ),
                    protocol=network.ApplicationGatewayProtocol.HTTPS,
                    ssl_profile=network.SubResourceArgs(
                        id=self.build_resource_id(
                            resource_provider_namespace="Microsoft.Network",
                            parent_resource_type="applicationGateways",
                            parent_resource_name=name,
                            resource_type="sslProfiles",
                            resource_name=f"{name}-ssl-profile",
                        )
                    ),
                    ssl_certificate=network.SubResourceArgs(
                        id=self.build_resource_id(
                            resource_provider_namespace="Microsoft.Network",
                            parent_resource_type="applicationGateways",
                            parent_resource_name=name,
                            resource_type="sslCertificates",
                            resource_name=f"{name}-ssl-cert",
                        )
                    ),
                ),
                network.ApplicationGatewayHttpListenerArgs(
                    name=name,
                    frontend_ip_configuration=network.SubResourceArgs(
                        id=self.build_resource_id(
                            resource_provider_namespace="Microsoft.Network",
                            parent_resource_type="applicationGateways",
                            parent_resource_name=name,
                            resource_type="frontendIpConfigurations",
                            resource_name=f"{name}-fe-ip-conf",
                        ),
                    ),
                    frontend_port=network.SubResourceArgs(
                        id=self.build_resource_id(
                            resource_provider_namespace="Microsoft.Network",
                            parent_resource_type="applicationGateways",
                            parent_resource_name=name,
                            resource_type="frontendPorts",
                            resource_name=f"{name}-80",
                        ),
                    ),
                    protocol=network.ApplicationGatewayProtocol.HTTP,
                ),
            ],
            request_routing_rules=[
                network.ApplicationGatewayRequestRoutingRuleArgs(
                    name=name,
                    rule_type=network.ApplicationGatewayRequestRoutingRuleType.BASIC,
                    backend_address_pool=network.SubResourceArgs(
                        id=self.build_resource_id(
                            resource_provider_namespace="Microsoft.Network",
                            parent_resource_type="applicationGateways",
                            parent_resource_name=name,
                            resource_type="backendAddressPools",
                            resource_name=bap_name,
                        ),
                    ),
                    backend_http_settings=network.SubResourceArgs(
                        id=self.build_resource_id(
                            resource_provider_namespace="Microsoft.Network",
                            parent_resource_type="applicationGateways",
                            parent_resource_name=name,
                            resource_type="backendHttpSettingsCollection",
                            resource_name=f"{name}-be-http-settings",
                        ),
                    ),
                    http_listener=network.SubResourceArgs(
                        id=self.build_resource_id(
                            resource_provider_namespace="Microsoft.Network",
                            parent_resource_type="applicationGateways",
                            parent_resource_name=name,
                            resource_type="httpListeners",
                            resource_name=name,
                        )
                    ),
                )
            ],
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service=get_stack(), role="application-gateway", group=name),
            opts=ResourceOptions(parent=parent),
        )

        return GatewayExports(
            name=name,
            backend_address_pool_name=bap_name,
        )
