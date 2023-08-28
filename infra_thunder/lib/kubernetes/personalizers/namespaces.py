from pulumi import ResourceOptions, ComponentResource
from pulumi_kubernetes import core, meta

DEFAULT_NAMESPACES = ["frontend", "backend"]


class Namespaces(ComponentResource):
    """
    Configure the default namespaces and add any extras from the cluster configuration
    """

    def __init__(self, name: str, extra_namespaces: list[str], opts: ResourceOptions = None):
        super().__init__(
            f"pkg:thunder:kubernetes:personalizers:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )

        for ns in DEFAULT_NAMESPACES:
            self._add_namespace(ns)

        for ns in extra_namespaces:
            self._add_namespace(ns)

    def _add_namespace(self, ns: str):
        core.v1.Namespace(
            f"{ns}",
            metadata=meta.v1.ObjectMetaArgs(
                name=ns,
            ),
            opts=ResourceOptions(parent=self),
        )
