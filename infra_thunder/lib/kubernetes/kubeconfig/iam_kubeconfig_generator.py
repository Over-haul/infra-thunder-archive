from base64 import b64encode
from pathlib import Path

from jinja2 import Template
from pulumi import log, Output, Input


def generate_iam_kubeconfig(cls, cluster_name: Input[str], endpoint: Input[str], ca_cert: Input[str]) -> Output[str]:
    """
    Generate a user kubeconfig for an IAM-enabled cluster.
    This function generates a Pulumi Output so it can be used by other Pulumi functions and properly awaited.

    :return: Output[str] kubeconfig YAML document
    """

    def _do_generate_kubeconfig(args: list[Output]) -> str:
        # gotta tuple unpack args because the function signature of apply() returns a list of lists
        cluster_name, endpoint, ca_cert = args

        kubeconfig_tpl = Path(__file__).parent / "iam_kubeconfig.tpl.yaml"

        with open(kubeconfig_tpl) as tpl:
            kubeconfig = Template(tpl.read()).render(
                {
                    "cluster_name": cluster_name,
                    "endpoint": endpoint,
                    "ca_cert_b64": b64encode(ca_cert.encode(encoding="ascii")).decode(encoding="ascii"),
                }
            )

        log.debug(
            f"# Thunder has generated an IAM kubeconfig for you\n" f"\n{kubeconfig}",
            resource=cls,
        )

        # Return the rendered string version
        return kubeconfig

    awaited_config = Output.all(cluster_name, endpoint, ca_cert).apply(_do_generate_kubeconfig)

    # Return the Output[str] to be resolved by whomever needs it
    return awaited_config
