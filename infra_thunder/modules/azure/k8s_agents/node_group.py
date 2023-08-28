from abc import ABC

from pulumi import ComponentResource, get_stack, ResourceOptions
from pulumi_azure_native import compute, network

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.azure.iam import assign_sysenv_vm_roles, VMRoleAssignmentArgs
from infra_thunder.lib.azure.image import get_image
from infra_thunder.lib.azure.keypairs import (
    get_admin_username,
    get_admin_key_path,
    get_keypair,
)
from infra_thunder.lib.azure.network import get_subnet, SubnetPurpose
from infra_thunder.lib.user_data import UserData
from .config import NodeGroup, GatewayExports


class NodeGroupMixin(AzureModule, ABC):
    def build_node_group(
        self,
        config: NodeGroup,
        default_gateway: GatewayExports,
        extra_gateways: list[GatewayExports],
        asg: network.ApplicationSecurityGroup,
        nsg: network.NetworkSecurityGroup,
        pod_nsg: network.NetworkSecurityGroup,
        parent: ComponentResource,
    ) -> compute.VirtualMachineScaleSet:
        image = get_image("ivy-kubernetes")

        main_subnet = get_subnet(
            purpose=SubnetPurpose.MAIN,
            resource_group_name=self.resourcegroup.name,
        )

        pod_subnet = get_subnet(purpose=SubnetPurpose.PODS, resource_group_name=self.resourcegroup.name)

        indexed_extra_gateways = {gw.name: gw for gw in extra_gateways}

        gateways = [
            *([default_gateway] if config.include_default_gateway else []),
            *[indexed_extra_gateways[gw_name] for gw_name in config.extra_gateways],
        ]

        vmss = compute.VirtualMachineScaleSet(
            config.name,
            sku=compute.SkuArgs(
                capacity=config.count,
                name=config.instance_type,
                tier="Standard",
            ),
            upgrade_policy=compute.UpgradePolicyArgs(mode=compute.UpgradeMode.MANUAL),
            overprovision=False,
            identity=compute.VirtualMachineScaleSetIdentityArgs(type=compute.ResourceIdentityType.SYSTEM_ASSIGNED),
            virtual_machine_profile=compute.VirtualMachineScaleSetVMProfileArgs(
                os_profile=compute.VirtualMachineScaleSetOSProfileArgs(
                    computer_name_prefix=get_stack(),
                    admin_username=get_admin_username(),
                    custom_data=UserData(
                        f"{config.name}-user-data",
                        include_defaults=True,
                        include_cloudconfig=True,
                        base64_encode=True,
                        replacements={},
                        opts=ResourceOptions(parent=self),
                    ).template,
                    linux_configuration=compute.LinuxConfigurationArgs(
                        disable_password_authentication=True,
                        ssh=compute.SshConfigurationArgs(
                            public_keys=[
                                compute.SshPublicKeyArgs(
                                    path=get_admin_key_path(),
                                    key_data=get_keypair(resource_group_name=self.resourcegroup.name).public_key,
                                )
                            ]
                        ),
                    ),
                ),
                network_profile=compute.VirtualMachineScaleSetNetworkProfileArgs(
                    network_interface_configurations=[
                        compute.VirtualMachineScaleSetNetworkConfigurationArgs(
                            name=f"{config.name}-primary",
                            network_security_group=compute.SubResourceArgs(
                                id=nsg.id,
                            ),
                            primary=True,
                            # enable_accelerated_networking=True
                            enable_ip_forwarding=True,
                            ip_configurations=[
                                compute.VirtualMachineScaleSetIPConfigurationArgs(
                                    name=config.name,
                                    primary=True,
                                    subnet=compute.SubResourceArgs(
                                        id=main_subnet.id,
                                    ),
                                    application_security_groups=[
                                        compute.SubResourceArgs(
                                            id=asg.id,
                                        )
                                    ],
                                    application_gateway_backend_address_pools=[
                                        compute.SubResourceArgs(
                                            id=self.build_resource_id(
                                                resource_provider_namespace="Microsoft.Network",
                                                parent_resource_type="applicationGateways",
                                                parent_resource_name=gw.name,
                                                resource_type="backendAddressPools",
                                                resource_name=gw.backend_address_pool_name,
                                            ),
                                        )
                                        for gw in gateways
                                    ],
                                )
                            ],
                        ),
                        compute.VirtualMachineScaleSetNetworkConfigurationArgs(
                            name=f"{config.name}-pods",
                            network_security_group=compute.SubResourceArgs(
                                id=pod_nsg.id,
                            ),
                            primary=False,
                            # enable_accelerated_networking=True
                            enable_ip_forwarding=True,
                            ip_configurations=[
                                compute.VirtualMachineScaleSetIPConfigurationArgs(
                                    name=config.name,
                                    primary=True,
                                    subnet=compute.SubResourceArgs(
                                        id=pod_subnet.id,
                                    ),
                                )
                            ],
                        ),
                    ]
                ),
                storage_profile=compute.VirtualMachineScaleSetStorageProfileArgs(
                    image_reference=compute.ImageReferenceArgs(
                        id=image.id,
                    ),
                    os_disk=compute.OSDiskArgs(
                        create_option=compute.DiskCreateOptionTypes.FROM_IMAGE,
                        disk_size_gb=30,
                    ),
                ),
            ),
            **self.common_args,
            opts=ResourceOptions(parent=parent),
        )

        assign_sysenv_vm_roles(
            name=config.name,
            vm=vmss,
            additional_assignments=[
                VMRoleAssignmentArgs(
                    scope=self.resourcegroup.id,
                    role_definition_name="Network Contributor",
                )
            ],
        )

        return vmss
