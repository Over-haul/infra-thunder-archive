from dataclasses import dataclass


@dataclass
class KeyVaultConfig:
    secrets: dict[str, str]
    """
    Secrets in dict form -- the key being the name of the secret and the value a secret.
    Create using ``pulumi config set --path --secret "keyvault:secrets.SecretOne" MY_SECRET_ONE``
    """


@dataclass
class KeyVaultExports:
    secrets: list[str]
