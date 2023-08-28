from pulumi import get_stack
from pulumi_azure_native import network

from infra_thunder.lib.azure.base import AzureModule
from infra_thunder.lib.config import (
    get_public_sysenv_domain,
    get_public_base_domain,
)
from infra_thunder.lib.tags import get_tags
from .config import HostedZoneArgs, HostedZoneArgsList, HostedZoneExports


class DNSZones(AzureModule):
    def build(self, config: HostedZoneArgsList) -> list[HostedZoneExports]:
        public_base_domain = get_public_base_domain()
        sysenv_domain = get_public_sysenv_domain()

        config.sysenv_zone.name = sysenv_domain
        config.sysenv_zone.base_domain = public_base_domain

        for zone in config.extra_zones:
            zone.base_domain = zone.base_domain or sysenv_domain
            zone.name = f"{zone.name}.{zone.base_domain}"

        specs = [config.sysenv_zone] + config.extra_zones

        zones = [
            network.Zone(
                spec.name,
                zone_name=spec.name,
                zone_type=network.ZoneType.PUBLIC,
                location="global",  # dns is a global service in Azure so this is always global
                resource_group_name=self.resourcegroup.name,
                tags=get_tags(get_stack(), "zone", spec.name),
            )
            for spec in specs
        ]

        for spec, zone in zip(specs, zones):
            self._create_records(spec, zone)
            if spec.base_domain == config.sysenv_zone.name:
                self._parent_extras(sysenv_zone=zones[0], child_zone=zone, child_spec=spec)

        return [
            HostedZoneExports(
                fqdn=zone.name,
                name_servers=zone.name_servers,
                zone_id=zone.zone_name,
            )
            for zone in zones
        ]

    def _create_records(self, zone_spec: HostedZoneArgs, zone: network.Zone) -> None:
        """
        Creates records for a zone found in its zone spec.
        """
        for dns_record in zone_spec.records:
            kwargs = {
                "resource_name": f"{dns_record.name}.{zone_spec.name}",
                "relative_record_set_name": dns_record.name,
                "resource_group_name": self.resourcegroup.name,
                "record_type": dns_record.type,
                "ttl": dns_record.ttl,
                "zone_name": zone.name,
            }

            if dns_record.type == "A":
                kwargs["a_records"] = [network.ARecordArgs(ipv4_address=record) for record in dns_record.records]
            elif dns_record.type == "AAAA":
                kwargs["aaaa_records"] = [network.AaaaRecordArgs(ipv6_address=record) for record in dns_record.records]
            elif dns_record.type == "CNAME":
                kwargs["cname_record"] = network.CnameRecordArgs(cname=dns_record.records[0])
            elif dns_record.type == "TXT":
                kwargs["txt_records"] = [network.TxtRecordArgs(value=dns_record.records)]
            else:
                raise Exception(f"{dns_record.type} is not a valid DNS type")
            network.RecordSet(**kwargs)

    def _parent_extras(
        self,
        sysenv_zone: network.Zone,
        child_zone: network.Zone,
        child_spec: HostedZoneArgs,
    ) -> None:
        """
        Creates an NS record in the parent sysenv zone pointing to child subdomain zones.
        """
        network.RecordSet(
            resource_name=child_spec.name,
            resource_group_name=self.resourcegroup.name,
            relative_record_set_name=child_spec.name,
            ns_records=child_zone.name_servers.apply(
                lambda ns: [network.NsRecordArgs(nsdname=record) for record in ns]
            ),
            record_type="NS",
            ttl=60,
            zone_name=sysenv_zone.name,
        )
