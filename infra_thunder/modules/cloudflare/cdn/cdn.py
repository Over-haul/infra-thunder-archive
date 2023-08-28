from infra_thunder.lib.cloudflare.base import CloudflareModule
from .config import CloudflareArgs
from .config import CloudflareExports, ZoneExports, RuleExports, RecordExports
import pulumi_cloudflare as cloudflare


class CloudflareZone(CloudflareModule):
    def build(self, config: CloudflareArgs) -> CloudflareExports:
        return CloudflareExports(zones=[self._create_zone(zone) for zone in config.zones])

    def _create_zone(self, zone) -> ZoneExports:
        cdn_zone = cloudflare.Zone(zone.name, zone=zone.name)
        rules = [self._create_record(record, cdn_zone, zone.name) for record in zone.records or list()]
        page_rules = [self._create_page_rule(rule, cdn_zone.id, zone.name) for rule in zone.page_rules or list()]

        return ZoneExports(name=zone.name, id=cdn_zone.id, rules=rules, page_rules=page_rules)

    def _create_record(self, record, zone_id, zone_name) -> RecordExports:
        record = cloudflare.Record(
            f"{record.name}.{zone_name}",
            zone_id=zone_id,
            name=record.name,
            value=record.value,
            type=record.type.value,
            ttl=record.ttl,
            proxied=record.proxied,
        )
        return RecordExports(id=record.id)

    def _create_page_rule(self, rule, zone_id, zone_name) -> RuleExports:
        page_rule = cloudflare.PageRule(
            rule.target,
            zone_id=zone_id,
            target=rule.target,
            priority=rule.priority,
            actions=cloudflare.PageRuleActionsArgs(
                ssl=rule.ssl.value,
                always_use_https=rule.always_use_https,
                automatic_https_rewrites="on" if rule.automatic_https_rewrites else "off",
                browser_cache_ttl=rule.browser_cache_ttl,
                browser_check="on" if rule.browser_check else "off",
                cache_level=rule.cache_level.value,
                disable_apps=rule.disable_apps,
                disable_performance=rule.disable_performance,
                disable_security=rule.disable_security,
                disable_zaraz=rule.disable_zaraz,
                host_header_override=rule.host_header_override,
                ip_geolocation="on" if rule.ip_geolocation else "off",
                mirage="on" if rule.mirage else "off",
                polish=rule.polish.value,
                resolve_override=rule.resolve_override,
                rocket_loader="on" if rule.rocket_loader else "off",
            ),
        )
        return RuleExports(page_rule.id)
