import json

DATADOG_AUTODISCOVERY_NAMESPACE = "ad.datadoghq.com"


def get_datadog_annotations(container_name, check_type, check_config):
    """
    Returns the pod annotations used for Datadog monitoring discovery

    :param container_name: Name of the container from the list of containers in this pod to apply monitoring to
    :param check_type: Name of the datadog agent check to apply to the container
    :param check_config: Datadog agent check configuration for this container
    :return: Dict of pod annotations
    """
    return {
        f"{DATADOG_AUTODISCOVERY_NAMESPACE}/{container_name}.init_configs": "[{}]",
        f"{DATADOG_AUTODISCOVERY_NAMESPACE}/{container_name}.check_names": json.dumps([check_type]),
        f"{DATADOG_AUTODISCOVERY_NAMESPACE}/{container_name}.instances": json.dumps([check_config]),
    }


def get_prometheus_annotations():
    raise NotImplementedError("Prometheus support not implemented yet")
