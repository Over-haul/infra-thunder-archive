from enum import Enum


class CNIProviders(Enum):
    azure_cni = "azure-cni"
    cilium = "cilium"
