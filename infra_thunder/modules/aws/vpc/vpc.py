from pulumi import ResourceOptions, Output
from pulumi_aws import ec2

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import get_sysenv, get_internal_sysenv_domain
from infra_thunder.lib.tags import get_tags
from .config import VPCArgs, VPCExports
from .default_keypair import setup_default_keypair
from .internet_gateway import setup_igw
from .nat_gateway import setup_nat_gateways
from .network_acls import setup_network_acls
from .prefix_list import setup_prefix_list
from .security_groups import setup_security_groups
from .subnets import setup_subnets
from .types import SubnetAndConfig
from .vpc_endpoints import setup_vpc_endpoints


class VPC(AWSModule):
    def build(self, config: VPCArgs) -> VPCExports:
        if len(config.public_subnets) == 0 and len(config.private_subnets) == 0:
            raise Exception("No public or private subnets specified. Please add some.")

        # Create the VPC and DHCP option set
        vpc = self._create_vpc(config.cidr, config.secondary_cidrs)
        prefix_list, peered_prefix_list = setup_prefix_list(config.supernet, vpc)
        self._create_dhcp_options(vpc, config)

        # Create the public and private subnets
        # Type hints per PEP-0526 https://www.python.org/dev/peps/pep-0526/#global-and-local-variable-annotations
        public_subnets: list[SubnetAndConfig]
        public_routes: list[ec2.RouteTable]
        public_subnets, public_routes = setup_subnets(self.region, vpc, config.public_subnets, is_public=True)

        private_subnets: list[SubnetAndConfig]
        private_routes: list[ec2.RouteTable]
        private_subnets, private_routes = setup_subnets(self.region, vpc, config.private_subnets, is_public=False)

        # Create the NACLs
        setup_network_acls(vpc, list(map(lambda x: x.subnet, public_subnets + private_subnets)))

        # Create default security groups
        default_security_groups = setup_security_groups(vpc, prefix_list, peered_prefix_list, config)

        # Create VPC endpoints for S3/etc
        if config.create_endpoints:
            setup_vpc_endpoints(
                self.region,
                prefix_list,
                vpc,
                public_subnets + private_subnets,
                public_routes + private_routes,
            )

        # Set up the internet gateway
        setup_igw(vpc, public_subnets, public_routes)

        # Create NAT gateways if we have private subnets
        if len(private_subnets) > 0 and config.create_nat:
            setup_nat_gateways(vpc, public_subnets, private_subnets, private_routes)

        # Create default EC2 keypair
        keypair = setup_default_keypair(vpc)

        return VPCExports(
            vpc_id=vpc.id,
            supernet=config.supernet,
            cidrs=config.secondary_cidrs + [config.cidr],
            prefix_list=prefix_list.id,
            peered_prefix_list=peered_prefix_list.id,
            default_ssh_pubkey=keypair.public_key_openssh,
            default_ssh_privatekey=Output.secret(keypair.private_key_pem),
            private_subnets=[x.subnet.id for x in private_subnets],
            private_routes=[x.id for x in private_routes],
            public_subnets=[x.subnet.id for x in public_subnets],
            public_routes=[x.id for x in public_routes],
            default_security_groups=[x.id for x in default_security_groups],
        )

    def _create_vpc(self, cidr: str, secondary_cidrs: list[str] = None) -> ec2.Vpc:
        """
        Create the AWS VPC and the secondary CIDRs
        :return: VPC object
        """
        vpc = ec2.Vpc(
            "VPC",
            enable_dns_hostnames=True,
            enable_dns_support=True,
            cidr_block=cidr,
            tags=get_tags("VPC", get_sysenv()),
            opts=ResourceOptions(parent=self),
        )
        if secondary_cidrs:
            for secondary_cidr in secondary_cidrs:
                ec2.VpcIpv4CidrBlockAssociation(
                    f"cidr-{secondary_cidr}",
                    cidr_block=secondary_cidr,
                    vpc_id=vpc.id,
                    opts=ResourceOptions(parent=vpc),
                )
        return vpc

    def _create_dhcp_options(self, vpc: ec2.Vpc, config: VPCArgs) -> None:
        """
        Create DHCP Options and associate it with the VPC
        :param vpc: VPC object to associate to
        :return: None
        """
        dhcp_options = ec2.VpcDhcpOptions(
            "DHCPOptions",
            domain_name=config.domain_name or get_internal_sysenv_domain(),
            domain_name_servers=["AmazonProvidedDNS"],
            tags=get_tags("DHCPOptions", get_sysenv()),
            opts=ResourceOptions(parent=vpc),
        )
        ec2.VpcDhcpOptionsAssociation(
            "DHCPOptionsAssociation",
            vpc_id=vpc.id,
            dhcp_options_id=dhcp_options.id,
            opts=ResourceOptions(parent=vpc),
        )
