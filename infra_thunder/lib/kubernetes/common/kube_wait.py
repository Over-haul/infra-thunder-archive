import time

import yaml
from kubernetes import client, config
from kubernetes.client import ApiClient, Configuration, ApiException
from pulumi import ComponentResource, Input, log, ResourceOptions
from urllib3.exceptions import HTTPError


class KubeWaiter(ComponentResource):
    def __init__(self, name: str, kubeconfig: Input[str], opts: ResourceOptions = None):
        super().__init__(
            f"pkg:thunder:kubernetes:{self.__class__.__name__.lower()}",
            name,
            None,
            opts,
        )
        kubeconfig.apply(self._wait_for_kube_api)

    def _wait_for_kube_api(self, kubeconfig: Input[str]):
        kube_client = client.CoreV1Api(api_client=new_client_from_string(config_string=kubeconfig))
        retries = 0
        while True:
            try:
                kube_client.get_api_resources()
            except (HTTPError, ApiException):
                if retries == 12:
                    raise
                log.warn(f"Unable to contact kube ApiServer at {kube_client.api_client.configuration.host}, retrying")
                time.sleep(10)
                retries = retries + 1
                pass


def new_client_from_string(config_string=None, context=None, persist_config=False):
    client_config = type.__call__(Configuration)
    config.load_kube_config_from_dict(
        config_dict=yaml.safe_load(config_string),
        context=context,
        client_configuration=client_config,
        persist_config=persist_config,
    )
    return ApiClient(configuration=client_config)
