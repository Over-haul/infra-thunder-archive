from pulumi import ComponentResource, ResourceOptions

from infra_thunder.lib.kubernetes.helm import HelmChartComponent, HelmChart


class AzureCiliumCNI(ComponentResource):
    """
    Configure CiliumCNI for Azure
    """

    def __init__(self, name: str, endpoint: str, opts: ResourceOptions = None):
        super().__init__(
            f"pkg:thunder:kubernetes:personalizers:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )

        # TODO: run the controller on the controllers only!!

        HelmChartComponent(
            "azure-cilium-cni",
            chart=HelmChart(
                chart="cilium",
                repo="https://helm.cilium.io/",
                version="1.10.5",
                namespace="kube-system",
                values={
                    "operator": {
                        "nodeSelector": {
                            # only run the operator on the control plane instances, as they are the only ones
                            # that have the required permissions to update the VMSS and read the network
                            "node-role.kubernetes.io/control-plane": ""
                        }
                    },
                    "azure": {
                        # enable the azure IPAM for allocating IPs as IPConfigurations
                        "enabled": True
                    },
                    "bpf": {
                        # allow routing to ClusterIP services over eth0
                        # this enables us to advertise ClusterIP services over BGP to flatten the network
                        "lbExternalClusterIP": True
                    },
                    # no need for NAT on pod outbound internet access, we have a NAT gateway
                    "enableIPv4Masquerade": False,
                    # turn on hubble
                    "hubble": {"relay": {"enabled": True}, "ui": {"enabled": True}},
                    # again, enable azure
                    "ipam": {"mode": "azure"},
                    # we're replacing kube-proxy, so we need to know how to get to the apiserver
                    "k8sServiceHost": endpoint,
                    "k8sServicePort": 443,
                    "kubeProxyReplacement": "strict",
                    # no need to enable nodeinit since it handles setting up the basic CNI drivers (loopback, etc)
                    # since we already bake those into the base images
                    "nodeinit": {"enabled": False},
                    # we want to use native routing, no tunnelling plx, kthx
                    "tunnel": "disabled",
                },
            ),
            opts=ResourceOptions(parent=self),
        )
