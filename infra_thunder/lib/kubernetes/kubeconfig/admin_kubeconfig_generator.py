from base64 import b64encode
from pathlib import Path

from jinja2 import Template
from pulumi import log, Output, Input


def generate_admin_kubeconfig(
    cls,
    cluster_name: Input[str],
    endpoint: Input[str],
    ca_cert: Input[str],
    admin_cert: Input[str],
    admin_key: Input[str],
) -> Output[str]:
    """
    Generate a admin kubeconfig for a PKI-based cluster using the admin certificate.
    This function generates a Pulumi Output so it can be used by other Pulumi functions and properly awaited.

    :return: Output[str] kubeconfig YAML document
    """

    def _do_generate_kubeconfig(args: list[Output]) -> str:
        # gotta tuple unpack args because the function signature of apply() returns a list of lists
        cluster_name, endpoint, ca_cert, admin_cert, admin_key = args

        kubeconfig_tpl = Path(__file__).parent / "admin_kubeconfig.tpl.yaml"

        with open(kubeconfig_tpl) as tpl:
            kubeconfig = Template(tpl.read()).render(
                {
                    "cluster_name": cluster_name,
                    "endpoint": endpoint,
                    "ca_cert_b64": b64encode(ca_cert.encode(encoding="ascii")).decode(encoding="ascii"),
                    "admin_cert_b64": b64encode(admin_cert.encode(encoding="ascii")).decode(encoding="ascii"),
                    "admin_key_b64": b64encode(admin_key.encode(encoding="ascii")).decode(encoding="ascii"),
                }
            )

        log.debug(
            f"# Thunder has generated an administrator kubeconfig for you\n" f"\n{kubeconfig}",
            resource=cls,
        )

        # Return the rendered string version
        return kubeconfig

    awaited_config = Output.all(cluster_name, endpoint, ca_cert, admin_cert, admin_key).apply(_do_generate_kubeconfig)

    # Return the Output[str] to be resolved by whomever needs it
    return awaited_config
