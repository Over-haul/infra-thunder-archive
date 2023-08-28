from pulumi import Output, ResourceOptions
from pulumi_aws import autoscaling, ebs, ec2, GetAmiFilterArgs, iam, ssm, route53
from pulumi_aws.ec2 import get_ami

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import (
    get_sysenv,
    get_stack,
    get_public_sysenv_domain,
    thunder_env,
)
from infra_thunder.lib.iam import (
    generate_instance_profile,
    generate_eni_policy,
    generate_ebs_policy,
)
from infra_thunder.lib.keypairs import get_keypair
from infra_thunder.lib.route_tables import get_route_tables
from infra_thunder.lib.security_groups import (
    ANY_IPV4_ADDRESS,
    get_default_security_groups,
    SecurityGroupIngressRule,
    generate_security_group,
)
from infra_thunder.lib.subnets import get_subnets_attributes
from infra_thunder.lib.tags import get_asg_tags, get_tags
from infra_thunder.lib.user_data import UserData
from infra_thunder.lib.vpc import get_vpc
from .config import PritunlArgs, PritunlExports


class Pritunl(AWSModule):
    def build(self, config: PritunlArgs) -> PritunlExports:
        vpc = get_vpc()
        hosted_zone = route53.get_zone(name=get_public_sysenv_domain(), private_zone=False)
        public_dns = f"vpn.{get_public_sysenv_domain()}"

        # Get the AMI
        ami = get_ami(
            owners=[thunder_env.get("ami_owner", "self")],
            most_recent=True,
            filters=[
                GetAmiFilterArgs(
                    name="name",
                    values=["ivy-pritunl*"],
                )
            ],
        )

        subnets = get_subnets_attributes(public=True, purpose="public", vpc_id=vpc.id)

        ingress_rules = [
            SecurityGroupIngressRule(
                description="Allow ping",
                from_port=-1,
                to_port=-1,
                protocol="icmp",
                cidr_blocks=[ANY_IPV4_ADDRESS],
            ),
            SecurityGroupIngressRule(
                description="http ui",
                from_port=80,
                to_port=80,
                protocol="tcp",
                cidr_blocks=[ANY_IPV4_ADDRESS],
            ),
            SecurityGroupIngressRule(
                description="https ui",
                from_port=443,
                to_port=443,
                protocol="tcp",
                cidr_blocks=[ANY_IPV4_ADDRESS],
            ),
            SecurityGroupIngressRule(
                description="VPN clients",
                from_port=10000,
                to_port=20000,
                protocol="udp",
                cidr_blocks=[ANY_IPV4_ADDRESS],
            ),
            SecurityGroupIngressRule(
                description="replies from local vpc",
                from_port=0,
                to_port=0,
                protocol="-1",
                allow_vpc_supernet=True,
            ),
        ]

        if config.allow_ssh_from_anywhere:
            ingress_rules.append(
                SecurityGroupIngressRule(
                    description="ssh",
                    from_port=22,
                    to_port=22,
                    protocol="tcp",
                    cidr_blocks=[ANY_IPV4_ADDRESS],
                )
            )

        policy_generators = {generate_eni_policy}
        ssm_pritunl_prefix = f"/Infrastructure/{get_sysenv()}/{get_stack()}/main"
        vol_id = ""

        if config.mongodb_uri:
            # this server uses another mongodb to connect
            ssm_connection_uri = f"{ssm_pritunl_prefix}/CONNECTION_URI"
            ssm.Parameter(
                f"{get_stack()}-connectionuri",
                name=ssm_connection_uri,
                type="SecureString",
                value=config.mongodb_uri,
            )
        else:
            # this server is a mongodb host, make a volume to store mongo data
            ssm_connection_uri = ""
            vol = ebs.Volume(
                get_stack(),
                availability_zone=subnets[0].availability_zone,
                size=config.data_volume_size if config.data_volume_size else 40,
                type=config.data_volume_type if config.data_volume_type else "gp2",
                tags=get_tags(get_stack(), "data-volume"),
            )
            vol_id = vol.id
            policy_generators.add(generate_ebs_policy(vol))

            # we should allow others to access our mongodb
            ingress_rules.append(
                SecurityGroupIngressRule(
                    description="mongodb master",
                    from_port=27017,
                    to_port=27017,
                    protocol="tcp",
                    allow_vpc_supernet=True,
                    allow_peered_supernets=True,
                )
            )

        security_group = generate_security_group(
            ingress_rules=ingress_rules,
            name=get_stack(),
            opts=ResourceOptions(parent=self),
        )

        eni = ec2.NetworkInterface(
            get_stack(),
            subnet_id=subnets[0].id,
            security_groups=[security_group.id] + get_default_security_groups(vpc_id=vpc.id).ids,
            source_dest_check=False,
            tags=get_tags(get_stack(), "eni"),
            opts=ResourceOptions(parent=security_group),
        )

        eip = ec2.Eip(
            get_stack(),
            network_interface=eni.id,
            vpc=True,
            opts=ResourceOptions(parent=eni),
        )

        route53.Record(
            get_stack(),
            zone_id=hosted_zone.zone_id,
            name=public_dns,
            type="A",
            ttl=300,
            records=[eip.public_ip],
            opts=ResourceOptions(parent=eip),
        )

        # Set up the routing table for the VPC
        route_tables = get_route_tables(vpc_id=vpc.id).ids
        [
            ec2.Route(
                f"{get_stack()}-{client_subnet}-{route_table}",
                route_table_id=route_table,
                destination_cidr_block=client_subnet,
                network_interface_id=eni.id,
                opts=ResourceOptions(parent=eni),
            )
            for client_subnet in config.client_subnets
            for route_table in route_tables
        ]

        instance_profile, instance_role = generate_instance_profile(
            self,
            include_default=True,
            policy_generators=policy_generators,
            name=get_stack(),
        )

        iam.RolePolicy(
            f"{get_stack()}-ssm",
            role=instance_role.id,
            policy={
                "Statement": [
                    {
                        "Sid": "ssmAccess",
                        "Effect": "Allow",
                        "Action": ["ssm:*"],
                        "Resource": [
                            f"arn:{self.partition}:ssm:{self.region}:{self.aws_account_id}:parameter{ssm_pritunl_prefix}/*"
                        ],
                    },
                    {
                        "Sid": "listAllZones",
                        "Effect": "Allow",
                        "Action": ["route53:ListHostedZones"],
                        "Resource": "*",
                    },
                    {
                        "Sid": "certbotValidation",
                        "Effect": "Allow",
                        "Action": [
                            "route53:GetChange",
                            "route53:ChangeResourceRecordSets",
                        ],
                        "Resource": [
                            Output.concat("arn:aws:route53:::hostedzone/", hosted_zone.zone_id),
                            "arn:aws:route53:::change/*",
                        ],
                    },
                ]
            },
            opts=ResourceOptions(parent=instance_role),
        )

        lt = ec2.LaunchTemplate(
            get_stack(),
            update_default_version=True,
            iam_instance_profile=ec2.LaunchTemplateIamInstanceProfileArgs(arn=instance_profile.arn),
            ebs_optimized=True,
            key_name=get_keypair(),
            user_data=UserData(
                get_stack(),
                include_defaults=True,
                include_cloudconfig=True,
                base64_encode=True,
                replacements={
                    "server_id": config.server_id,
                    "ssm_connection_uri": ssm_connection_uri,
                    "ebs_id": vol_id,
                },
                opts=ResourceOptions(parent=self, depends_on=[eni]),
            ).template,
            image_id=ami.id,
            instance_type=config.instance_type,
            network_interfaces=[ec2.LaunchTemplateNetworkInterfaceArgs(network_interface_id=eni.id)],
            tags=get_tags(get_stack(), "launch-template"),
            tag_specifications=[
                ec2.LaunchTemplateTagSpecificationArgs(
                    resource_type="instance", tags=get_tags(get_stack(), "instance")
                ),
                ec2.LaunchTemplateTagSpecificationArgs(
                    resource_type="volume", tags=get_tags(get_stack(), "root-volume")
                ),
            ],
            opts=ResourceOptions(parent=instance_profile),
        )

        autoscaling.Group(
            get_stack(),
            launch_template=autoscaling.GroupLaunchTemplateArgs(id=lt.id, version="$Latest"),
            availability_zones=[subnets[0].availability_zone],
            suspended_processes=[
                "ReplaceUnhealthy",
            ],
            max_size=1,
            min_size=0,
            tags=get_asg_tags(get_stack(), "auto-scaling-group"),
            opts=ResourceOptions(parent=lt),
        )

        return PritunlExports(
            public_dns=public_dns,
            public_ip=eip.public_ip,
            private_ip=eip.private_ip,
            client_subnets=config.client_subnets,
            mongodb_uri=config.mongodb_uri,
            server_id=config.server_id,
        )
