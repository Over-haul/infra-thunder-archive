from pulumi import log


def interpolate_resource(cls, resource: str) -> str:
    """
    Interpolate resource identifiers from config to allow access to the full set of parameters provided by AWS

    Example:
        "arn:{partition}:kinesis:{aws_account_id}::abc/queue-123"
        becomes
        "arn:aws:kinesis:1234567890::abc/queue-123"

    This function requires the calling class to implement the interpolated functions, and thererfore is extremely
    simple. However, at a later date this function may add additional functionality and may be hoisted into the
    set of library functions for use by other modules.

    :param cls: Calling class to interpolate from
    :param resource: Resource string to interpolate
    :return: Interpolated resource string
    """
    interpolated = resource.format(**cls.__dict__)
    log.debug(f"interpolating role: [{resource}] to [{interpolated}]")
    return interpolated
