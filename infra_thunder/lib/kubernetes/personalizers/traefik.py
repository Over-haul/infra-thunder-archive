from pulumi import ResourceOptions, ComponentResource

from infra_thunder.lib.config import get_sysenv, thunder_env
from infra_thunder.lib.kubernetes.helm import HelmChartComponent, HelmChart


class Traefik(ComponentResource):
    """
    Configure Traefik
    """

    def __init__(self, name: str, opts: ResourceOptions = None):
        super().__init__(
            f"pkg:thunder:kubernetes:personalizers:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )

        supernet = thunder_env.get("network_supernet")

        HelmChartComponent(
            "traefik",
            chart=HelmChart(
                chart="traefik",
                repo="https://helm.traefik.io/traefik",
                version="9.14.2",
                namespace="kube-system",
                values={
                    "deployment": {
                        # deploy traefik to all nodes
                        "kind": "DaemonSet",
                        # use cluster dns provider but hostnet for talking to services
                        "dnsPolicy": "ClusterFirstWithHostNet",
                    },
                    # no need for a service, traefik will be :8080 on every node
                    "service": {"enabled": False},
                    # use host network, change the port, and disable exposing the port via docker's nat
                    "hostNetwork": True,
                    "ports": {"web": {"port": 8080, "expose": False}},
                    "globalArguments": [
                        # this allows x-forwarded-* headers to be passed by the ALB to traefik
                        f"--entryPoints.web.forwardedHeaders.trustedIPs={supernet}",
                        # enable sending metrics to datadog via the locally installed agent
                        "--metrics.datadog.address=127.0.0.1:8125",
                        # disable ssl verify so ExternalName can talk directly to ALBs
                        "--serversTransport.insecureSkipVerify=true",
                        # enable send spans to datadog-tracing-agent at this address
                        "--tracing.datadog.localAgentHostPort=127.0.0.1:8126",
                        # set environment tag for all datadog spans
                        f"--tracing.datadog.globalTag=env:{get_sysenv()}",
                        # enable access logs
                        "--accesslog=true",
                    ],
                },
            ),
            opts=ResourceOptions(parent=self),
        )
