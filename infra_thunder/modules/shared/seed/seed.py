from pulumi import Output
from pulumi_random.random_id import RandomId

from infra_thunder.lib.shared.base import SharedModule
from .config import SeedConfig, SeedExports


class Seed(SharedModule):
    def build(self, config: SeedConfig) -> SeedExports:
        if config.seed_override:
            seed = Output.from_input(config.seed_override)
        else:
            random_id = RandomId("seed", byte_length=config.byte_length)
            seed_b64 = random_id.b64_url

            seed = seed_b64.apply(lambda v: v.lower().replace("_", "").replace("-", ""))

        return SeedExports(seed=seed)
