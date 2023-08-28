import ipaddress

import pulumi_kubernetes
from pulumi import Output, ResourceOptions, ComponentResource
from pulumi_azure_native import storage, keyvault, network
from pulumi_azuread import application

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.azure.dns_zones import get_sysenv_zone
from infra_thunder.lib.azure.iam import assign_sysenv_vm_roles, VMRoleAssignmentArgs
from infra_thunder.lib.azure.image import get_image, get_gallery
from infra_thunder.lib.azure.network import get_subnet, SubnetPurpose
from infra_thunder.lib.config import (
    get_sysenv,
    get_stack,
    get_public_sysenv_domain,
    tag_namespace,
)
from infra_thunder.lib.kubernetes.kubeconfig import generate_admin_kubeconfig
from infra_thunder.lib.tags import get_tags
from .aad import create_kubernetes_aad
from .cluster_personalizer import AzureClusterPersonalizer
from .config import (
    K8sControllerConfig,
    K8sControllerExports,
    K8sControllerAgentSecretsExports,
)
from .keyvault import create_vault
from .lb import create_lb
from .nsg import create_pod_nsg, create_controller_asg_and_nsg
from .pki import (
    create_kubernetes_rootca,
    create_kubernetes_proxy_rootca,
    create_etcd_root_ca,
    create_admin_client_cert,
    create_service_account_keypair,
)
from .vmss import create_vmss


class K8sControllers(AzureModule):
    def build(self, config: K8sControllerConfig) -> K8sControllerExports:
        cluster_name = get_sysenv()
        cluster_domain = f"{cluster_name}.{tag_namespace}"

        # Create component resource to group things together
        cluster_component = ComponentResource(
            f"pkg:thunder:azure:{self.__class__.__name__.lower()}:cluster",
            cluster_name,
            None,
            opts=ResourceOptions(parent=self),
        )

        # Create blob storage account for backups
        backups_container = self._create_backups_container(cluster_component)

        # Create the CAs for the controllers to use at boot to issue certs
        root_key, root_cert = create_kubernetes_rootca(self, cluster_component, cluster_name)
        proxy_key, proxy_cert = create_kubernetes_proxy_rootca(self, cluster_component, cluster_name)
        etcd_root_key, etcd_root_ca = create_etcd_root_ca(self, cluster_component, cluster_name)

        # Create the admin key and cert (this lives in the pulumi statefile only, and is used to create the admin kubeconfig)
        admin_key, admin_cert = create_admin_client_cert(self, cluster_component, root_key, root_cert)

        # Create the service account keypair
        sa_key = create_service_account_keypair(self, cluster_component)

        # Create a key vault for the CA certificate and any common secrets required for agents to bootstrap
        agent_secrets = {
            "CA-CRT": root_cert.cert_pem,
        }
        agent_vault, agent_secret_uris = create_vault(self, cluster_component, "agents", agent_secrets)

        # Create a controllers-only key vault
        controller_secrets = {
            "CA-KEY": root_key.private_key_pem,
            # ca crt not here to avoid duplication
            "PROXY-CA-KEY": proxy_key.private_key_pem,
            "PROXY-CA-CRT": proxy_cert.cert_pem,
            "ETCD-CA-KEY": etcd_root_key.private_key_pem,
            "ETCD-CA-CRT": etcd_root_ca.cert_pem,
            "SERVICE-ACCOUNT-KEY": sa_key.private_key_pem,
            "SERVICE-ACCOUNT-PEM": sa_key.public_key_pem,
        }
        controller_vault, controller_secret_uris = create_vault(
            self, cluster_component, "controllers", controller_secrets
        )

        # Merge the secret uris list so the userdata only has a single list to iterate through (`|` is merge dicts in py3.9)
        merged_secret_uris = controller_secret_uris | agent_secret_uris

        # Assign the CoreDNS clusterIP
        coredns_clusterip = str(ipaddress.ip_network(config.service_cidr)[config.coredns_clusterip_index])

        # Create pod network security group
        pod_nsg = create_pod_nsg(self, cluster_component)

        # create the endpoint dns name
        sysenv_domain = get_public_sysenv_domain()
        endpoint_prefix = "controller"
        internal_endpoint_prefix = f"int-{endpoint_prefix}"
        internal_endpoint = f"{internal_endpoint_prefix}.{sysenv_domain}"
        lb_endpoint = f"{endpoint_prefix}.{sysenv_domain}"

        # get the subnets where we're going to run a controller
        subnet = get_subnet(purpose=SubnetPurpose.MAIN, resource_group_name=self.resourcegroup.name)
        pod_subnet = get_subnet(purpose=SubnetPurpose.PODS, resource_group_name=self.resourcegroup.name)

        # create the load balancer for etcd and apiserver
        lb, lb_pool = create_lb(self, cluster_component, subnet)

        # create the controller lb dns name
        self._create_lb_endpoint(cluster_component, endpoint_prefix, lb)

        # create the controller internal dns RR name
        self._create_internal_endpoint(cluster_component, internal_endpoint_prefix)

        # create aad applications and bootstrapper msi
        apiserver_app, bootstrap_msi = create_kubernetes_aad(self, cluster_component, lb_endpoint)

        # create the controllers and the load balancer between them
        controller_vmss = self._create_controllers(
            cluster_component,
            coredns_clusterip,
            cluster_domain,
            config,
            controller_vault,
            agent_vault,
            merged_secret_uris,
            internal_endpoint,
            lb_endpoint,
            subnet,
            pod_subnet,
            pod_nsg,
            lb_pool,
            apiserver_app,
        )

        # use the admin cert to make an admin kubeconfig
        kubeconfig = generate_admin_kubeconfig(
            self,
            cluster_name,
            lb_endpoint,
            root_cert.cert_pem,
            admin_cert.cert_pem,
            admin_key.private_key_pem,
        )

        # create a azure (user) kubeconfig for this cluster
        # azure_kubeconfig = generate_azure_kubeconfig(self, cluster_name, endpoint_name, root_cert.cert_pem)

        # setup the clusterip routes
        # if config.enable_clusterip_bgp:
        #     # assign the kube-router pod IP
        #     kube_router_podip = str(
        #         ipaddress.ip_network()
        #     )
        #     create_clusterip_virtual_router(self, subnet, controller_eni, cluster_config)

        # TODO: create cluster health component to prevent personalize_cluster from entering parallel retry loop
        # (This component would make a curl to /healthz of one of the k8s controllers and return success when that page is available)

        # use the admin kubeconfig to personalize the cluster via helm charts and fetch some values we want to export
        k8s_provider = pulumi_kubernetes.Provider(
            "k8s-provider",
            kubeconfig=kubeconfig.future(),
            # context=cluster_config.name,
            opts=ResourceOptions(
                parent=cluster_component,
                depends_on=[controller_vmss],
            ),
        )
        AzureClusterPersonalizer(
            f"{get_stack()}-personalizer",
            cluster_name=cluster_name,
            cluster_domain=cluster_domain,
            cluster_config=config,
            endpoint_name=internal_endpoint,
            # bootstrap_role=None,
            # user_roles=None,
            coredns_clusterip=coredns_clusterip,
            bootstrap_msi=bootstrap_msi,
            opts=ResourceOptions(provider=k8s_provider, parent=cluster_component),
        )

        # Export them for the launcher to register as a StackOutput
        return K8sControllerExports(
            name=cluster_name,
            endpoint=lb_endpoint,
            internal_endpoint=internal_endpoint,
            service_cidr=config.service_cidr,
            coredns_clusterip=coredns_clusterip,
            cluster_domain=cluster_domain,
            pod_nsg=pod_nsg.id,
            # bootstrap_msi=bootstrap_role.arn,
            admin_kubeconfig=kubeconfig,
            agent_secrets=K8sControllerAgentSecretsExports(vault_id=agent_vault.id, vault_secrets=agent_secret_uris),
            agent_bootstrap_msi_id=bootstrap_msi.id
            # iam_kubeconfig=iam_kubeconfig
        )

    def _create_backups_container(self, dependency: ComponentResource) -> storage.BlobContainer:
        account = storage.StorageAccount(
            "controllers",
            kind=storage.Kind.STORAGE_V2,
            sku=storage.SkuArgs(
                name=storage.SkuName.STANDARD_ZRS,
            ),
            access_tier=storage.AccessTier.HOT,
            is_hns_enabled=False,
            enable_nfs_v3=False,
            allow_blob_public_access=False,
            allow_shared_key_access=True,
            **self.common_args,
            tags=get_tags(service=get_stack(), role="backups"),
            opts=ResourceOptions(parent=dependency),
        )

        container = storage.BlobContainer(
            "backups",
            container_name="backups",
            account_name=account.name,
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(parent=account),
        )

        return container

    def _create_controllers(
        self,
        dependency: ComponentResource,
        coredns_clusterip: str,
        cluster_domain: str,
        cluster_config: K8sControllerConfig,
        controller_vault: keyvault.Vault,
        agent_vault: keyvault.Vault,
        secret_uris: dict[str, Output[str]],
        internal_endpoint: str,
        lb_endpoint: str,
        subnet: network.AwaitableGetSubnetResult,
        pod_subnet: network.AwaitableGetSubnetResult,
        pod_nsg: network.NetworkSecurityGroup,
        lb_pool: str,
        aad_apiserver_app: application.Application,
    ):
        # Find our image
        image = get_image("ivy-kubernetes")

        # create the controllers nsg
        controller_asg, controller_nsg = create_controller_asg_and_nsg(self, dependency)

        # make the VM scale set
        vmss = create_vmss(
            self,
            dependency,
            cluster_config,
            image,
            controller_asg,
            controller_nsg,
            pod_nsg,
            subnet,
            pod_subnet,
            lb_pool,
            internal_endpoint,
            lb_endpoint,
            secret_uris,
            coredns_clusterip,
            cluster_domain,
            aad_apiserver_app,
        )

        # Assign roles to the controllers
        roles = [
            # Allow the VMSS to read the controller secrets
            VMRoleAssignmentArgs(scope=controller_vault.id, role_definition_name="Key Vault Secrets User"),
            # Allow the VMSS to read the agent secrets
            VMRoleAssignmentArgs(scope=agent_vault.id, role_definition_name="Key Vault Secrets User"),
            # Allow the VMSS to find other instances in it's pool
            # TODO: this role is ridiculously open, scope it down ASAP!
            VMRoleAssignmentArgs(
                scope=self.resourcegroup.id,
                role_definition_name="Virtual Machine Contributor",
            ),
            # TODO: for some reason cilium can't update the VMSS without access to the image gallery where the image is stored
            VMRoleAssignmentArgs(scope=get_gallery().id, role_definition_name="Reader"),
            # Allow the VMSS to update DNS records in this resource group
            # TODO: can you scope this to the dns zone id?
            VMRoleAssignmentArgs(scope=self.resourcegroup.id, role_definition_name="DNS Zone Contributor"),
        ]
        assign_sysenv_vm_roles(get_stack(), vmss, roles)

        return vmss

    def _create_lb_endpoint(
        self,
        dependency: ComponentResource,
        endpoint_name: str,
        controller_lb: network.LoadBalancer,
    ):
        zone = get_sysenv_zone(resource_group_name=self.resourcegroup.name)

        network.RecordSet(
            get_stack(),
            relative_record_set_name=endpoint_name,
            record_type="A",
            a_records=[
                network.ARecordArgs(ipv4_address=controller_lb.frontend_ip_configurations[0].private_ip_address)
            ],
            ttl=60,
            zone_name=zone.name,
            resource_group_name=self.resourcegroup.name,
            opts=ResourceOptions(parent=dependency),
        )

    def _create_internal_endpoint(self, dependency: ComponentResource, endpoint_name: str):
        zone = get_sysenv_zone(resource_group_name=self.resourcegroup.name)

        network.RecordSet(
            f"{get_stack()}-internal",
            relative_record_set_name=endpoint_name,
            record_type="A",
            a_records=[],
            ttl=10,
            zone_name=zone.name,
            resource_group_name=self.resourcegroup.name,
            # ignore the content of the A-records in this endpoint, as they are mutated by the VMSS on start
            opts=ResourceOptions(parent=dependency, ignore_changes=["aRecords"]),
        )
