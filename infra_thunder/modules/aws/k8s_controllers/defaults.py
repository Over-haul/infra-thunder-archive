from infra_thunder.lib.kubernetes.helm.config import HelmChart

from .types import IamAuthenticatorRole

default_roles: list[IamAuthenticatorRole] = [
    IamAuthenticatorRole(name="admin", permissions=["system:masters"]),
]

# Default namespaces to add to the cluster
default_namespaces = ["frontend", "backend"]

# Default helm charts to install
default_services = [
    # for auto approving kubelet serving csrs
    HelmChart(
        chart="kubelet-rubber-stamp",
        repo="https://flexkube.github.io/charts/",
        namespace="kube-system",
        version="0.1.7",
        values={
            # No values needed, flexkube's chart has a toleration for NoSchedule, and a nodeSelector for the controllers
        },
    ),
    # for allowing IAM namespaced (AssumeRole) pods
    HelmChart(
        chart="kube2iam",
        repo="https://jtblin.github.io/kube2iam/",
        namespace="kube-system",
        version="2.6.0",
        values={
            # allow running kube2iam on all instances, regardless of taint
            "tolerations": [{"operator": "Exists", "effect": "NoSchedule"}],
            "priorityClassName": "system-node-critical",
            "updateStrategy": "RollingUpdate",
            "resources": {
                "limits": {
                    "memory": "64Mi",
                }
            },
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
            "tolerations": [
                {
                    "key": "node-role.kubernetes.io/control-plane",
                    "operator": "Exists",
                    "effect": "NoSchedule",
                },
                {
                    "key": "node-role.kubernetes.io/master",
                    "operator": "Exists",
                    "effect": "NoSchedule",
                },
            ]
        },
    ),
]
