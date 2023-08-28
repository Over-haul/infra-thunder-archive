import ipaddress

from pulumi import ComponentResource, ResourceOptions
from pulumi_aws import ssm, route53, s3, sqs

from infra_thunder.lib.ami import get_ami
from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import tag_namespace, get_public_sysenv_domain
from infra_thunder.lib.kubernetes.kubeconfig import (
    generate_admin_kubeconfig,
    generate_iam_kubeconfig,
)
from infra_thunder.lib.s3 import generate_bucket_name
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_tags, get_sysenv, get_stack
from infra_thunder.lib.vpc import get_vpc
from .autoscaling_group import create_autoscaling_group
from .clusterip_routes import create_clusterip_routes
from .config import K8sControllerConfig, K8sControllerArgs, K8sControllerExports
from .defaults import default_roles
from .eventbridge import create_node_termination_eventbridge_rules
from .iam import (
    create_controller_role,
    create_node_bootstrap_role,
    create_user_role,
    create_ebs_controller_role,
    create_cluster_autoscaler_role,
    create_node_termination_handler_role,
)
from .personalizers import personalize_cluster
from .pki import (
    create_kubernetes_rootca,
    create_kubernetes_proxy_rootca,
    create_etcd_root_ca,
    create_admin_client_cert,
    create_service_account_keypair,
)
from .security_group import create_controller_security_group, create_pod_security_group
from .ssm import create_ssm_parameter
from .sqs import create_node_termination_sqs_queue


class K8sControllers(AWSModule):
    def __init__(self, name: str, config: K8sControllerConfig, opts: ResourceOptions = None):
        super().__init__(name, config, opts)

        self.backups_bucket = config.backups_bucket or generate_bucket_name(f"{get_stack()}-backups")

        self.e2d_snapshot_retention_time = config.e2d_snapshot_retention_time
        self.vpc = get_vpc()

    def build(self, config: K8sControllerConfig) -> list[K8sControllerExports]:
        # Create S3 backups bucket
        self._create_s3_backups_bucket(self.backups_bucket, exp=self.e2d_snapshot_retention_time)

        return [self._create_cluster(cluster_config) for cluster_config in config.clusters]

    def _create_cluster(self, cluster_config: K8sControllerArgs) -> K8sControllerExports:
        # Set cluster_config.name and cluster_config.cluster_domain if these are not set
        if cluster_config.name is None:
            cluster_config.name = get_sysenv()
        if cluster_config.cluster_domain is None:
            cluster_config.cluster_domain = f"{cluster_config.name}.{tag_namespace}"

        # Create component resource to group things together
        cluster_component = ComponentResource(
            f"pkg:thunder:aws:{self.__class__.__name__.lower()}:cluster:{cluster_config.name}",
            cluster_config.name,
            None,
            opts=ResourceOptions(parent=self),
        )

        # Create the CAs for the controllers to use at boot to issue certs
        root_key, root_cert = create_kubernetes_rootca(self, cluster_component, cluster_config)
        proxy_key, proxy_cert = create_kubernetes_proxy_rootca(self, cluster_component, cluster_config)
        etcd_root_key, etcd_root_ca = create_etcd_root_ca(self, cluster_component, cluster_config)

        # Create the admin key and cert (this lives in the pulumi statefile only, and is used to create the admin kubeconfig)
        admin_key, admin_cert = create_admin_client_cert(self, cluster_component, root_key, root_cert, cluster_config)

        # Create the service account keypair
        sa_key = create_service_account_keypair(self, cluster_component, cluster_config)

        # Save the parameters to SSM - if you change any of these names, make sure you change it in the userdata too!
        ssm_vars = [
            ("pki/ca.key", True, root_key.private_key_pem),
            ("pki/ca.crt", False, root_cert.cert_pem),
            ("pki/proxy-ca.key", True, proxy_key.private_key_pem),
            ("pki/proxy-ca.crt", False, proxy_cert.cert_pem),
            ("etcd/pki/ca.key", True, etcd_root_key.private_key_pem),
            ("etcd/pki/ca.crt", False, etcd_root_ca.cert_pem),
            ("pki/service_account.key", True, sa_key.private_key_pem),
            ("pki/service_account.pem", False, sa_key.public_key_pem),
        ]
        ssm_params = []
        for name, is_secret, value in ssm_vars:
            ssm_params.append(
                (
                    name,
                    create_ssm_parameter(self, cluster_component, name, value, is_secret, cluster_config),
                )
            )

        # Create SQS queue for AWS node termination handler
        node_termination_handler_queue = create_node_termination_sqs_queue(self, cluster_component, cluster_config)
        # Create eventbridge rule for node termination handler
        create_node_termination_eventbridge_rules(
            self, cluster_component, node_termination_handler_queue, cluster_config
        )

        # Create management iam role and node bootstrapper role
        user_roles = [create_user_role(self, cluster_component, role, cluster_config) for role in default_roles]
        bootstrap_role = create_node_bootstrap_role(self, cluster_component, cluster_config)
        ebs_controller_role = create_ebs_controller_role(self, cluster_component, cluster_config)
        cluster_autoscaler_role = create_cluster_autoscaler_role(self, cluster_component, cluster_config)
        node_termination_handler_role = create_node_termination_handler_role(
            self, cluster_component, cluster_config, node_termination_handler_queue
        )

        # Assign the CoreDNS clusterIP
        coredns_clusterip = str(
            ipaddress.ip_network(cluster_config.service_cidr)[cluster_config.coredns_clusterip_index]
        )

        # create the controllers
        controller_asgs, endpoint_name, endpoints = self._create_controllers(
            cluster_component,
            coredns_clusterip,
            cluster_config,
            ssm_params,
            self.e2d_snapshot_retention_time,
        )

        # use the admin cert to make an admin kubeconfig
        kubeconfig = generate_admin_kubeconfig(
            self,
            cluster_config.name,
            endpoint_name,
            root_cert.cert_pem,
            admin_cert.cert_pem,
            admin_key.private_key_pem,
        )

        # create a iam (user) kubeconfig for this cluster
        iam_kubeconfig = generate_iam_kubeconfig(self, cluster_config.name, endpoint_name, root_cert.cert_pem)

        # Create pod security group
        pod_security_group = create_pod_security_group(self, cluster_component, cluster_config)

        # TODO: create cluster health component to prevent personalize_cluster from entering parallel retry loop
        # (This component would make a curl to /healthz of one of the k8s controllers and return success when that page is available)

        # use the admin kubeconfig to personalize the cluster via helm charts and fetch some values we want to export
        personalize_cluster(
            self,
            cluster_component,
            controller_asgs,
            endpoint_name,
            bootstrap_role,
            user_roles,
            [pod_security_group],
            coredns_clusterip,
            ebs_controller_role,
            cluster_autoscaler_role,
            node_termination_handler_role,
            node_termination_handler_queue,
            kubeconfig,
            cluster_config,
        )

        # Export them for the launcher to register as a StackOutput

        return K8sControllerExports(
            name=cluster_config.name,
            endpoint=endpoint_name,
            service_cidr=cluster_config.service_cidr,
            coredns_clusterip=coredns_clusterip,
            cluster_domain=cluster_config.cluster_domain,
            bootstrap_role_arn=bootstrap_role.arn,
            admin_kubeconfig=kubeconfig,
            iam_kubeconfig=iam_kubeconfig,
            is_admin_cert_expired=admin_cert.ready_for_renewal,
        )

    def _create_s3_backups_bucket(self, bucket_name: str, exp: int):
        bucket = s3.Bucket(
            bucket_name,
            bucket=bucket_name,
            acl="private",
            versioning=s3.BucketVersioningArgs(enabled=False),
            tags=get_tags(get_stack(), "bucket", bucket_name),
            lifecycle_rules=[
                s3.BucketLifecycleRuleArgs(
                    enabled=True,
                    abort_incomplete_multipart_upload_days=0,
                    expiration=s3.BucketLifecycleRuleExpirationArgs(days=exp, expired_object_delete_marker=False),
                    id=f"E2DLifecycle-{get_sysenv()}/",
                    prefix=f"{get_sysenv()}/",
                ),
            ],
            opts=ResourceOptions(parent=self),
        )
        s3.BucketPublicAccessBlock(
            bucket_name,
            bucket=bucket.id,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
            opts=ResourceOptions(parent=bucket),
        )
        return bucket

    def _create_controllers(
        self,
        dependency: ComponentResource,
        coredns_clusterip: str,
        cluster_config: K8sControllerArgs,
        ssm_params: list[tuple[str, ssm.Parameter]],
        e2d_snapshot_retention_time: int,
    ):
        # Find our AMI
        ami = get_ami("ivy-kubernetes")

        # IAM and security group
        controller_profile, controller_role = create_controller_role(
            self, dependency, self.backups_bucket, cluster_config
        )
        controller_security_group = create_controller_security_group(self, dependency, cluster_config)

        # get the subnets where we're going to run a controller
        subnets = get_subnets_attributes(public=False, purpose="private", vpc_id=self.vpc.id)

        # Route53 variables
        sysenv_domain = get_public_sysenv_domain()
        zone_id = route53.get_zone(name=sysenv_domain).id
        if cluster_config.name == get_sysenv():
            endpoint_name = f"controller.{sysenv_domain}"
        else:
            endpoint_name = f"controller.{cluster_config.name}.{sysenv_domain}"

        controller_asgs = []
        controller_ips = []
        endpoints = []

        # limit controllers to 3 - if we have more private subnets just use the first three (etcd doesn't understand more)
        for subnet in subnets[:3]:
            # Make the controllers!
            controller_asg, controller_eni = create_autoscaling_group(
                self,
                dependency,
                ami,
                subnet,
                controller_profile,
                controller_security_group,
                endpoint_name,
                ssm_params,
                coredns_clusterip,
                self.backups_bucket,
                cluster_config,
                e2d_snapshot_retention_time,
            )

            # setup the clusterip routes
            if cluster_config.enable_clusterip_routes:
                create_clusterip_routes(self, subnet, controller_eni, cluster_config)

            # Make per-controller endpoint DNS records
            controller_endpoint = f"{subnet.availability_zone}.{endpoint_name}"
            route53.Record(
                f"endpoint-{subnet.availability_zone}",
                name=controller_endpoint,
                type="A",
                ttl=300,
                records=[controller_eni.private_ip],
                zone_id=zone_id,
                opts=ResourceOptions(parent=dependency),
            )
            controller_asgs.append(controller_asg)
            endpoints.append(controller_endpoint)
            controller_ips.append(controller_eni.private_ip)

        # Create the cluster round robin endpoint
        endpoint = route53.Record(
            "endpoint",
            name=endpoint_name,
            zone_id=zone_id,
            type="A",
            ttl=300,
            records=controller_ips,
            opts=ResourceOptions(parent=dependency),
        )

        return controller_asgs, endpoint.name, endpoints
