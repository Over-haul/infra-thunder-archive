from dataclasses import dataclass


@dataclass
class Statement:
    Effect: str
    """AWS statement effect, ("Allow", "Deny")"""

    Action: list[str]
    """AWS action, ("s3:read", "s3:write",...)"""

    Resource: list[str]
    """
    AWS resources to apply this statement to.
    String interpolated to allow access to things like ``partition`` and ``aws_account_id``.

    See ``resource_interpolator.py`` for supported interpolations.
    """


@dataclass
class RolePolicy:
    name: str
    """Name of the IAM policy statement"""

    statements: list[Statement]
    """List of statements for this policy"""
