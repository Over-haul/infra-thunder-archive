from pulumi_kubernetes import provider as kubernetes_provider


def configure_csr_renewal(provider: kubernetes_provider.Provider):
    """
    Configure a ClusterRoleBinding that allows the Kubelets to renew their kubelet-serving CSRs
    :param cluster_config: Kubernetes Cluster Configuration
    :param provider: Kubernetes provider
    :return:
    """
    """
# Approve renewal CSRs for the group "system:nodes"
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: auto-approve-renewals-for-nodes
subjects:
- kind: Group
  name: system:nodes
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: system:certificates.k8s.io:certificatesigningrequests:selfnodeclient
  apiGroup: rbac.authorization.k8s.io
    """
    pass
