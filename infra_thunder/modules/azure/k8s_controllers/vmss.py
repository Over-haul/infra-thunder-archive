import ipaddress

from pulumi import ResourceOptions, ComponentResource, get_stack, Output
from pulumi_azure_native import compute, network
from pulumi_azuread import application

from infra_thunder.lib.azure.client import get_tenant_id
from infra_thunder.lib.azure.keypairs import (
    get_admin_key_path,
    get_keypair,
    get_admin_username,
)
from infra_thunder.lib.config import get_public_sysenv_domain
from infra_thunder.lib.tags import get_tags, get_sysenv
from infra_thunder.lib.user_data import UserData
from .config import K8sControllerConfig


def create_vmss(
    cls,
    dependency: ComponentResource,
    cluster_config: K8sControllerConfig,
    image: compute.GetGalleryImageResult,
    controller_asg: network.ApplicationSecurityGroup,
    controller_nsg: network.NetworkSecurityGroup,
    pod_nsg: network.NetworkSecurityGroup,
    subnet: network.AwaitableGetSubnetResult,
    pod_subnet: network.AwaitableGetSubnetResult,
    pool: str,
    internal_endpoint: str,
    lb_endpoint: str,
    secrets: dict[str, Output[str]],
    coredns_clusterip: str,
    cluster_domain: str,
    aad_apiserver_app: application.Application,
):
    # create vmss
    # assign user defined roles to allow assuming MSI for k8s controllers(?)
    # assign permissions to the VMSS to allow it to list tags
    vmss = compute.VirtualMachineScaleSet(
        get_stack(),
        vm_scale_set_name=get_stack(),
        sku=compute.SkuArgs(
            capacity=3,  # no more, no less
            name=cluster_config.instance_type,
            tier="Standard",  # no enum?
        ),
        upgrade_policy=compute.UpgradePolicyArgs(mode=compute.UpgradeMode.MANUAL),
        overprovision=False,  # do not overprovision controllers, etcd MUST have 3
        identity=compute.VirtualMachineScaleSetIdentityArgs(
            # include a system managed identity
            type=compute.ResourceIdentityType.SYSTEM_ASSIGNED
        ),
        virtual_machine_profile=compute.VirtualMachineScaleSetVMProfileArgs(
            diagnostics_profile=compute.DiagnosticsProfileArgs(
                boot_diagnostics=compute.BootDiagnosticsArgs(
                    # enable instance screenshot and serial console
                    enabled=True
                )
            ),
            os_profile=compute.VirtualMachineScaleSetOSProfileArgs(
                # azure computer name will be `k8s-controllers-000002`
                # azure vm "name" will be `k8s-controllers_2`
                # we will set the hostname to be `k8s-controllers-2` in userdata by getting vm name and replacing underscore
                computer_name_prefix=get_stack() + "-",
                admin_username=get_admin_username(),
                custom_data=UserData(
                    get_stack(),
                    include_defaults=True,
                    include_cloudconfig=True,
                    base64_encode=True,
                    replacements={
                        "lb_endpoint": lb_endpoint,
                        "internal_endpoint": internal_endpoint,
                        "sysenv_zone": get_public_sysenv_domain(),
                        "cluster_name": get_sysenv(),
                        "vault_secrets": secrets,
                        "service_cidr": cluster_config.service_cidr,
                        "api_service_ip": ipaddress.ip_network(cluster_config.service_cidr)[1],
                        "cluster_domain": cluster_domain,
                        "cluster_dns": coredns_clusterip,
                        # "backups_path": f"s3://{backups_bucket}/{cluster_config.name}/",
                        "dd_forward_audit_logs": str(cluster_config.dd_forward_audit_logs).lower(),
                        # "e2d_snapshot_retention_time": f"{e2d_snapshot_retention_time * 24}h"
                        "oidc_issuer_url": f"https://sts.windows.net/{get_tenant_id()}/",
                        "oidc_client_id": aad_apiserver_app.application_id,
                    },
                    opts=ResourceOptions(parent=cls),
                ).template,
                linux_configuration=compute.LinuxConfigurationArgs(
                    disable_password_authentication=True,
                    ssh=compute.SshConfigurationArgs(
                        public_keys=[
                            compute.SshPublicKeyArgs(
                                path=get_admin_key_path(),
                                key_data=get_keypair(resource_group_name=cls.resourcegroup.name).public_key,
                            )
                        ]
                    ),
                ),
            ),
            network_profile=compute.VirtualMachineScaleSetNetworkProfileArgs(
                network_interface_configurations=[
                    compute.VirtualMachineScaleSetNetworkConfigurationArgs(
                        name="primary",
                        network_security_group=compute.SubResourceArgs(
                            id=controller_nsg.id,
                        ),
                        primary=True,
                        # enable_accelerated_networking=True
                        enable_ip_forwarding=True,
                        ip_configurations=[
                            compute.VirtualMachineScaleSetIPConfigurationArgs(
                                name="ipconfig1",
                                primary=True,
                                subnet=compute.SubResourceArgs(
                                    id=subnet.id,
                                ),
                                application_security_groups=[
                                    compute.SubResourceArgs(
                                        id=controller_asg.id,
                                    )
                                ],
                                load_balancer_backend_address_pools=[
                                    compute.SubResourceArgs(
                                        id=pool,
                                    )
                                ],
                            )
                        ],
                    ),
                    compute.VirtualMachineScaleSetNetworkConfigurationArgs(
                        name="pods",
                        network_security_group=compute.SubResourceArgs(
                            id=pod_nsg.id,
                        ),
                        primary=False,
                        # enable_accelerated_networking=True
                        enable_ip_forwarding=True,
                        ip_configurations=[
                            compute.VirtualMachineScaleSetIPConfigurationArgs(
                                name="ipconfig1",
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
        **cls.common_args,
        tags=get_tags(service=get_stack(), role="instance"),
        opts=ResourceOptions(parent=dependency),
    )

    return vmss
