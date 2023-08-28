from pulumi import ResourceOptions, ComponentResource
from pulumi_tls import locally_signed_cert, private_key, self_signed_cert, cert_request

from infra_thunder.lib.tags import get_sysenv
from .config import K8sControllerArgs

TEN_YEARS_IN_HOURS = 87600
ONE_YEAR_IN_HOURS = 8760


def create_kubernetes_rootca(
    cls, dependency: ComponentResource, cluster_config: K8sControllerArgs
) -> (private_key.PrivateKey, self_signed_cert.SelfSignedCert):
    """
    Generate a Certificate Authority for issuing Kubernetes-related certificates

    :param cls: Parent class
    :param cluster_config: Kubernetes Cluster Configuration
    :return: Private Key and Certificate Authority
    """
    k8s_key = private_key.PrivateKey("ca", algorithm="RSA", rsa_bits=2048, opts=ResourceOptions(parent=dependency))
    k8s_ca = self_signed_cert.SelfSignedCert(
        "ca",
        private_key_pem=k8s_key.private_key_pem,
        validity_period_hours=TEN_YEARS_IN_HOURS,
        is_ca_certificate=True,
        subject=cert_request.SelfSignedCertSubjectArgs(
            common_name=f"Kubernetes Cluster {cluster_config.name} Root CA 1",
            organization="Thunder",
            organizational_unit=f"{get_sysenv()}",
            country="US",
        ),
        allowed_uses=[
            "key_encipherment",
            "digital_signature",
            "cert_signing",
        ],
        opts=ResourceOptions(parent=k8s_key),
    )

    return k8s_key, k8s_ca


def create_kubernetes_proxy_rootca(
    cls, dependency: ComponentResource, cluster_config: K8sControllerArgs
) -> (private_key.PrivateKey, self_signed_cert.SelfSignedCert):
    """
    Generate a Certificate Authority for issuing Kubernetes proxy (apiserver aggregation) related certificates

    :param cls: Parent class
    :param cluster_config: Kubernetes Cluster Configuration
    :return: Private Key and Certificate Authority
    """
    k8s_proxy_key = private_key.PrivateKey(
        "proxy-ca",
        algorithm="RSA",
        rsa_bits=2048,
        opts=ResourceOptions(parent=dependency),
    )
    k8s_proxy_ca = self_signed_cert.SelfSignedCert(
        "proxy-ca",
        private_key_pem=k8s_proxy_key.private_key_pem,
        validity_period_hours=TEN_YEARS_IN_HOURS,
        is_ca_certificate=True,
        subject=cert_request.SelfSignedCertSubjectArgs(
            common_name=f"Kubernetes Cluster {cluster_config.name} Proxy Root CA 1",
            organization="Thunder",
            organizational_unit=f"{get_sysenv()}",
            country="US",
        ),
        allowed_uses=[
            "key_encipherment",
            "digital_signature",
            "cert_signing",
        ],
        opts=ResourceOptions(parent=k8s_proxy_key),
    )

    return k8s_proxy_key, k8s_proxy_ca


def create_etcd_root_ca(
    cls, dependency: ComponentResource, cluster_config: K8sControllerArgs
) -> (private_key.PrivateKey, self_signed_cert.SelfSignedCert):
    """
    Generate a Certificate Authority for issuing certificates for an etcd cluster

    :param cls: Parent class
    :param cluster_config: Kubernetes Cluster Configuration
    :return: Private Key and Certificate Authority
    """
    etcd_key = private_key.PrivateKey(
        "etcd-ca",
        algorithm="RSA",
        rsa_bits=2048,
        opts=ResourceOptions(parent=dependency),
    )
    etcd_ca = self_signed_cert.SelfSignedCert(
        "etcd-ca",
        private_key_pem=etcd_key.private_key_pem,
        validity_period_hours=TEN_YEARS_IN_HOURS,
        is_ca_certificate=True,
        subject=cert_request.SelfSignedCertSubjectArgs(
            common_name=f"etcd Cluster {cluster_config.name} Root CA 1",
            organization="Thunder",
            organizational_unit=get_sysenv(),
            country="US",
        ),
        allowed_uses=[
            "key_encipherment",
            "digital_signature",
            "cert_signing",
        ],
        opts=ResourceOptions(parent=etcd_key),
    )

    return etcd_key, etcd_ca


def create_admin_client_cert(
    cls,
    dependency: ComponentResource,
    k8s_key: private_key.PrivateKey,
    k8s_ca: self_signed_cert.SelfSignedCert,
    cluster_config: K8sControllerArgs,
) -> (private_key.PrivateKey, locally_signed_cert.LocallySignedCert):
    """
    Issue an administrator-level client certificate against the Kubernetes CA

    :param cls: Parent class
    :param k8s_key: Kubernetes CA Private Key
    :param k8s_ca: Kubernetes CA
    :param cluster_config: Kubernetes Cluster Config
    :return: Private Key and Client Certificate
    """
    admin_key = private_key.PrivateKey(
        "cluster-admin",
        algorithm="RSA",
        rsa_bits=2048,
        opts=ResourceOptions(parent=dependency),
    )
    admin_csr = cert_request.CertRequest(
        "cluster-admin",
        private_key_pem=admin_key.private_key_pem,
        subject=cert_request.CertRequestSubjectArgs(
            common_name="kubernetes-admin",
            organization="system:masters",
            organizational_unit=get_sysenv(),
            country="US",
        ),
        opts=ResourceOptions(parent=admin_key),
    )
    admin_cert = locally_signed_cert.LocallySignedCert(
        "cluster-admin",
        is_ca_certificate=False,
        ca_cert_pem=k8s_ca.cert_pem,
        ca_private_key_pem=k8s_key.private_key_pem,
        # This cert expires in 1 year - thunder will auto renew it
        # it is not used by the cluster under normal circumstances so it expiring is not harmful, and is a good safety measure.
        early_renewal_hours=int(ONE_YEAR_IN_HOURS * 0.25),
        validity_period_hours=ONE_YEAR_IN_HOURS,
        cert_request_pem=admin_csr.cert_request_pem,
        allowed_uses=[
            "key_encipherment",
            "digital_signature",
            "client_auth",
        ],
        opts=ResourceOptions(parent=k8s_ca),
    )

    return admin_key, admin_cert


def create_service_account_keypair(
    cls, dependency: ComponentResource, cluster_config: K8sControllerArgs
) -> private_key.PrivateKey:
    return private_key.PrivateKey("sa", algorithm="RSA", rsa_bits=2048, opts=ResourceOptions(parent=dependency))
