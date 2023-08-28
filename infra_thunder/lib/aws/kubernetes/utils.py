def get_ssm_path(cluster_name: str):
    """
    Return the path to the SSM configuration keys for this cluster.
    The stack name is hardcoded here since it will be accessed by other stacks, and `get_stack()` is dynamic.

    :param cluster_name:
    :return:
    """
    return f"k8s-controllers/{cluster_name}"
