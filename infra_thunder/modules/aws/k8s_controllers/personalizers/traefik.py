from pulumi import ResourceOptions
from pulumi_kubernetes import provider as kubernetes_provider

from infra_thunder.lib.config import get_sysenv, tag_namespace
from infra_thunder.lib.kubernetes.constants import SPOT_TAG_KEY, DEDICATED_TAG_KEY
from infra_thunder.lib.kubernetes.helm import HelmChartStack
from infra_thunder.lib.kubernetes.helm.config import HelmChart
from infra_thunder.lib.vpc.ec2_get_prefix_list import get_prefix_list
from ..config import K8sControllerArgs


def configure_traefik(provider: kubernetes_provider.Provider, cluster_config: K8sControllerArgs):
    supernet_cidrs = ",".join(map(lambda x: x.cidr, get_prefix_list().entries))
    HelmChartStack(
        "traefik",
        namespace=cluster_config.name,
        chart=HelmChart(
            chart="traefik",
            repo="https://helm.traefik.io/traefik",
            version="10.7.1",
            namespace="kube-system",
            values={
                "priorityClassName": "system-node-critical",
                "deployment": {
                    # deploy traefik to all nodes
                    "kind": "DaemonSet",
                    # use cluster dns provider but hostnet for talking to services
                    "dnsPolicy": "ClusterFirstWithHostNet",
                },
                "resources": {
                    "limits": {
                        "cpu": "256m",
                        "memory": "128Mi",
                    }
                },
                "tolerations": [
                    # ensure traefik runs on every node (controllers, dedicated nodes, etc).
                    # this prevents us from accidentally creating a 'dedicated' nodegroup attached to a targetgroup
                    # that doesn't run traefik, which would lead to alb errors
                    # TODO: change "operator" back to "Exists" once cloud-lifecycle-controller listens on different port on controllers
                    {
                        "key": f"{tag_namespace}/{SPOT_TAG_KEY}",
                        "operator": "Exists",
                        "effect": "NoSchedule",
                    },
                    {
                        "key": f"{tag_namespace}/{DEDICATED_TAG_KEY}",
                        "operator": "Exists",
                        "effect": "NoSchedule",
                    },
                ],
                # no need for a service, traefik will be :8080 on every node
                "service": {"enabled": False},
                # use host network, change the port, and disable exposing the port via docker's nat
                "hostNetwork": True,
                "ports": {"web": {"port": 8080, "expose": False}},
                "globalArguments": [
                    # these allow the ALB to continue sending traffic to the containers
                    # for some time while it waits to read the failure from /ping
                    "--entrypoints.web.transport.lifecycle.gracetimeout=10",
                    "--entrypoints.web.transport.lifecycle.requestacceptgracetimeout=30",
                    # this allows x-forwarded-* headers to be passed by the ALB to traefik
                    f"--entryPoints.web.forwardedHeaders.trustedIPs={supernet_cidrs}",
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
        opts=ResourceOptions(parent=provider, provider=provider),
    )
