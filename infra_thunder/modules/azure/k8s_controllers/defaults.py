from infra_thunder.lib.kubernetes.helm.config import HelmChart

# Default namespaces to add to the cluster
default_namespaces = ["frontend", "backend"]

# Default helm charts to install
default_services = [
    # for auto approving kubelet serving csrs
    HelmChart(
        chart="kubelet-rubber-stamp",
        repo="https://flexkube.github.io/charts/",
        namespace="kube-system",
        version="0.1.6",
        values={
            # TODO: need to add node-role to control planes to allow it to run this container...
        },
    ),
    # for allowing IAM namespaced (AssumeRole) pods
    HelmChart(
        chart="kube2iam",
        repo="https://jtblin.github.io/kube2iam/",
        namespace="kube-system",
        version="2.6.0",
        values={
            # allow running kube2iam on control plane
            "tolerations": [{"operator": "Exists", "effect": "NoSchedule"}],
            "host": {
                "iptables": True,
                "interface": "eni+",
            },  # TODO: what happens if using cilium? - move this to the CNI?
        },
    ),
    # because a picture is worth a thousand words
    HelmChart(
        chart="kubernetes-dashboard",
        repo="https://kubernetes.github.io/dashboard/",
        namespace="kube-system",
        version="4.0.0",
        values={
            # allow running kubernetes-dashboard on control plane
            "tolerations": [{"operator": "Exists", "effect": "NoSchedule"}]
        },
    ),
]
