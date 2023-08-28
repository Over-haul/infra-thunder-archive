from pulumi import ResourceOptions, get_stack
from pulumi_aws import route53 as aws_route53

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import get_public_sysenv_domain, thunder_env
from infra_thunder.lib.tags import get_tags
from .config import HostedZoneArgs, HostedZoneArgsList, HostedZoneExports


class HostedZone(AWSModule):
    def build(self, config: HostedZoneArgsList) -> list[HostedZoneExports]:
        public_base_domain = thunder_env.require("public_base_domain")  # example.com
        sysenv_domain = get_public_sysenv_domain()  # sysenv.example.com

        config.sysenv_zone.name = sysenv_domain
        config.sysenv_zone.base_domain = public_base_domain

        for zone in config.extra_zones:
            zone.base_domain = zone.base_domain or sysenv_domain
            zone.name = f"{zone.name}.{zone.base_domain}"

        zones = self._create_zones(config)

        return [
            HostedZoneExports(
                fqdn=zone.name,
                name_servers=zone.name_servers,
                zone_id=zone.zone_id,
            )
            for zone in zones
        ]

    def _create_zones(self, config: HostedZoneArgsList) -> list[aws_route53.Zone]:
        """
        Creates zones, records, and parents any necessary subdomains to the sysenv.
        """
        specs = [config.sysenv_zone] + config.extra_zones

        zones = [
            aws_route53.Zone(
                spec.name,
                comment=spec.comment,
                name=spec.name,
                tags=get_tags(get_stack(), "zone", spec.name),
            )
            for spec in specs
        ]

        zone_pairs = list(zip(specs, zones))
        [self._create_records(spec, zone) for spec, zone in zone_pairs]
        # parent the zones if required
        [
            self._parent_extras(sysenv_zone=zones[0], child_zone=child_zone, child_spec=child_spec)
            for child_spec, child_zone in zone_pairs
            if child_spec.base_domain == config.sysenv_zone.name
        ]

        return zones

    def _create_records(self, zone_spec: HostedZoneArgs, zone: aws_route53.Zone) -> None:
        """
        Creates records for a zone found in its zone spec.
        """
        [
            aws_route53.Record(
                f"{dns_record.name}.{zone_spec.name}",
                zone_id=zone.id,
                name=f"{dns_record.name}.{zone_spec.name}",
                type=dns_record.type,
                records=[record for record in dns_record.records],
                ttl=dns_record.ttl,
                opts=ResourceOptions(parent=zone),
            )
            for dns_record in zone_spec.records
        ]

    def _parent_extras(
        self,
        sysenv_zone: aws_route53.Zone,
        child_zone: aws_route53.Zone,
        child_spec: HostedZoneArgs,
    ) -> None:
        """
        Creates an NS record in the parent sysenv zone pointing to child subdomain zones.
        """
        aws_route53.Record(
            child_spec.name,
            zone_id=sysenv_zone.id,
            name=child_spec.name,
            type="NS",
            records=child_zone.name_servers,
            ttl=60,
            opts=ResourceOptions(parent=sysenv_zone),
        )
