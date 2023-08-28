from dataclasses import dataclass
from enum import Enum


@dataclass
class IamAuthenticatorRole:
    name: str
    permissions: list[str]


class CNIProviders(Enum):
    aws_cni = "aws-cni"
    cilium = "cilium"
