from pulumi import ResourceOptions, get_stack
from pulumi_azure_native import compute, network, keyvault, authorization

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.azure.client import get_tenant_id
from infra_thunder.lib.azure.iam import assign_sysenv_vm_roles
from infra_thunder.lib.azure.keypairs import (
    get_keypair,
    get_admin_username,
    get_admin_key_path,
)
from infra_thunder.lib.azure.network import get_subnet, get_route_table
from infra_thunder.lib.azure.network.constants import SubnetPurpose
from infra_thunder.lib.config import thunder_env
from infra_thunder.lib.tags import get_tags
from infra_thunder.lib.user_data import UserData
from .config import PritunlArgs, PritunlExports


class Pritunl(AzureModule):
    def build(self, config: PritunlArgs) -> PritunlExports:
        # create the public ip address
        ip = network.PublicIPAddress(
            "pritunl-publicip",
            public_ip_allocation_method=network.IPAllocationMethod.STATIC,
            sku=network.PublicIPAddressSkuArgs(
                name=network.PublicIPAddressSkuName.STANDARD,
                tier=network.PublicIPAddressSkuTier.REGIONAL,
            ),
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="pritunl", role="publicip"),
            opts=ResourceOptions(parent=self),
        )

        # create the dns record
        # TODO: we need a wrapper function here to add it to the private and public zones!
        # TODO: re-enable this once the dns module is written
        # network.RecordSet(
        #     "pritunl-dnsrecord",
        #     relative_record_set_name="vpn",
        #     zone_name=get_public_sysenv_domain(),
        #     record_type="A",
        #     # does this work??
        #     target_resource=network.SubResourceArgs(
        #         id=ip.id
        #     ),
        #     ttl=3600.0,
        #     resource_group_name=self.resourcegroup.name,
        #     opts=ResourceOptions(parent=ip)
        # )

        # create the network security group
        sg = network.NetworkSecurityGroup(
            "pritunl-nsg",
            security_rules=[
                # allow ping from the internet
                network.SecurityRuleArgs(
                    priority=200,
                    name="Internet-Ping",
                    access=network.SecurityRuleAccess.ALLOW,
                    direction=network.SecurityRuleDirection.INBOUND,
                    protocol=network.SecurityRuleProtocol.ICMP,
                    source_address_prefix="*",
                    source_port_range="*",
                    destination_address_prefix="*",
                    destination_port_range="*",
                ),
                # allow openvpn server ports from internet
                network.SecurityRuleArgs(
                    priority=210,
                    name="Internet-OpenVPN",
                    access=network.SecurityRuleAccess.ALLOW,
                    direction=network.SecurityRuleDirection.INBOUND,
                    protocol=network.SecurityRuleProtocol.UDP,
                    source_address_prefix="*",
                    source_port_range="*",
                    destination_address_prefix="*",
                    destination_port_range="10000-20000",
                ),
                # allow ssh from internet
                network.SecurityRuleArgs(
                    priority=220,
                    name="Internet-SSH",
                    access=network.SecurityRuleAccess.ALLOW,
                    direction=network.SecurityRuleDirection.INBOUND,
                    protocol=network.SecurityRuleProtocol.TCP,
                    source_address_prefix="*",
                    source_port_range="*",
                    destination_address_prefix="*",
                    destination_port_range="22",
                ),
                # allow pritunl webui ports from internet
                network.SecurityRuleArgs(
                    priority=230,
                    name="Internet-PritunlUI",
                    access=network.SecurityRuleAccess.ALLOW,
                    direction=network.SecurityRuleDirection.INBOUND,
                    protocol=network.SecurityRuleProtocol.TCP,
                    source_address_prefix="*",
                    source_port_range="*",
                    destination_address_prefix="*",
                    destination_port_ranges=["80", "443"],
                ),
                # allow all traffic from vnet (allows replies)
                network.SecurityRuleArgs(
                    priority=240,
                    name="VNET-All",
                    access=network.SecurityRuleAccess.ALLOW,
                    direction=network.SecurityRuleDirection.INBOUND,
                    protocol=network.SecurityRuleProtocol.ASTERISK,
                    source_address_prefix="VirtualNetwork",
                    source_port_range="*",
                    destination_address_prefix="*",
                    destination_port_range="*",
                ),
                # allow mongodb from all peered subnets
                network.SecurityRuleArgs(
                    priority=250,
                    name="Supernet-MongoDB",
                    access=network.SecurityRuleAccess.ALLOW,
                    direction=network.SecurityRuleDirection.INBOUND,
                    protocol=network.SecurityRuleProtocol.TCP,
                    source_address_prefix=thunder_env.get("network_supernet"),  # TODO: this needs a different name
                    source_port_range="*",
                    destination_address_prefix="*",
                    destination_port_range="27017",
                ),
                # last rule to nullify non-removable default nsg rules
                # Azure adds an allow rule for all traffic from the Azure LB and VNet - this is not desirable
                # as it could unintentionally allow access to ports that are not specified above
                network.SecurityRuleArgs(
                    priority=4000,
                    name="Last-Rule-Deny",
                    description="Last rule in the chain. This prevents unintentional access via the AllowVnetInBound "
                    "and AllowAzureLoadBalancerInBound default rules.",
                    access=network.SecurityRuleAccess.DENY,
                    direction=network.SecurityRuleDirection.INBOUND,
                    protocol=network.SecurityRuleProtocol.ASTERISK,
                    source_address_prefix="*",
                    source_port_range="*",
                    destination_address_prefix="*",
                    destination_port_range="*",
                ),
            ],
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(parent=self),
        )

        # create the nic - enable ip forwarding
        nic = network.NetworkInterface(
            "pritunl-nic",
            enable_ip_forwarding=True,
            # enable_accelerated_networking=True,
            ip_configurations=[
                network.NetworkInterfaceIPConfigurationArgs(
                    name="primary",
                    public_ip_address=network.PublicIPAddressArgs(id=ip.id),
                    subnet=network.SubnetArgs(
                        id=get_subnet(
                            purpose=SubnetPurpose.PUBLIC,
                            resource_group_name=self.resourcegroup.name,
                        ).id
                    ),
                )
            ],
            network_security_group=network.NetworkSecurityGroupArgs(id=sg.id),
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            tags=get_tags(service="pritunl", role="nic"),
            opts=ResourceOptions(parent=self),
        )

        # create the data volume
        volume = compute.Disk(
            "pritunl-datavol",
            disk_size_gb=config.data_volume_size,
            # tier=
            creation_data=compute.CreationDataArgs(create_option=compute.DiskCreateOption.EMPTY),
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(parent=self),
        )

        # create routes to the appliance
        for client_subnet in config.client_subnets:
            network.Route(
                f"pritunl-route-{client_subnet}".replace("/", "_"),
                address_prefix=client_subnet,
                next_hop_type=network.RouteNextHopType.VIRTUAL_APPLIANCE,
                next_hop_ip_address=nic.ip_configurations[0].private_ip_address,
                route_table_name=get_route_table(resource_group_name=self.resourcegroup.name).name,
                resource_group_name=self.resourcegroup.name,
                opts=ResourceOptions(parent=nic),
            )

        vault = None
        secret = None
        if config.mongodb_uri:
            # create the key vault to store the mongo connection string
            vault = keyvault.Vault(
                "pritunl-vault",
                properties=keyvault.VaultPropertiesArgs(
                    tenant_id=get_tenant_id(),
                    enable_rbac_authorization=True,
                    sku=keyvault.SkuArgs(
                        name=keyvault.SkuName.STANDARD,
                        # ... "A"? Okay then.
                        family=keyvault.SkuFamily.A,
                    ),
                ),
                location=self.location,
                resource_group_name=self.resourcegroup.name,
                opts=ResourceOptions(parent=self),
            )
            secret = keyvault.Secret(
                "pritunl-mongo-uri",
                secret_name="mongo-connection-uri",  # pragma: allowlist secret
                properties=keyvault.SecretPropertiesArgs(
                    value=config.mongodb_uri,
                ),
                vault_name=vault.name,
                resource_group_name=self.resourcegroup.name,
                opts=ResourceOptions(parent=vault),
            )

        # create the single vm
        # TODO: this really needs to be made into a function. there's a lot of repetition here that could be eliminated
        vm = compute.VirtualMachine(
            "pritunl",
            identity=compute.VirtualMachineIdentityArgs(
                # include a system managed identity
                type=compute.ResourceIdentityType.SYSTEM_ASSIGNED
            ),
            hardware_profile=compute.HardwareProfileArgs(
                vm_size=config.instance_type,
            ),
            os_profile=compute.OSProfileArgs(
                computer_name="pritunl",
                admin_username=get_admin_username(),
                custom_data=UserData(
                    get_stack(),
                    include_defaults=True,
                    include_cloudconfig=True,
                    base64_encode=True,
                    replacements={
                        "server_id": config.server_id,
                        "mongo_connection_secret_uri": secret.properties.secret_uri if secret else "",
                    },
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
            network_profile=compute.NetworkProfileArgs(
                network_interfaces=[compute.NetworkInterfaceReferenceArgs(id=nic.id, primary=True)]
            ),
            storage_profile=compute.StorageProfileArgs(
                # TODO: this should use get_image library function once we have AMIs baked properly
                # TODO: does this trigger a replacement of the instance and any dependencies when replaced?
                image_reference=compute.ImageReferenceArgs(
                    # use id= if we need to reference a gallery image
                    publisher="Oracle",
                    offer="Oracle-Linux",
                    sku="ol83-lvm-gen2",
                    version="latest",
                ),
                os_disk=compute.OSDiskArgs(
                    create_option=compute.DiskCreateOptionTypes.FROM_IMAGE,
                    disk_size_gb=30,
                ),
                data_disks=[
                    compute.DataDiskArgs(
                        lun=1,
                        create_option=compute.DiskCreateOptionTypes.ATTACH,
                        managed_disk=compute.ManagedDiskParametersArgs(id=volume.id),
                    )
                ],
            ),
            location=self.location,
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(
                parent=nic,
                delete_before_replace=True,
            ),
        )

        assign_sysenv_vm_roles(name="pritunl", vm=vm)

        if secret:
            # if we created a secret earlier, allow the vm to access it
            authorization.RoleAssignment(
                "pritunl-vault-roleassignment",
                scope=vault.id,
                principal_id=vm.identity.principal_id,
                # this is required to assign a role to a system managed identity
                principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
                # TODO: this is ugly - need to write a library function to work around https://github.com/pulumi/pulumi-azure-native/issues/610
                # this library function could look like: https://github.com/pulumi/examples/blob/master/azure-py-call-azure-sdk/__main__.py#L16
                # this role definition is the 'Key Vault Secret Reader' roleDefinition
                role_definition_id="/providers/Microsoft.Authorization/roleDefinitions/4633458b-17de-408a-b874-0445c86b69e6",
                opts=ResourceOptions(parent=vm),
            )

        # firewall rule generator?? - allow ssh internal(??)

        # self.exports = all_galleries

        # self.register_outputs({get_stack(): {"galleries": [gallery.__dict__ for gallery in all_galleries]}})

        return None
