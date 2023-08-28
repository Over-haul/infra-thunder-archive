from .constants import (
    DEFAULT_KEY_PAIR_NAME,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ADMIN_KEY_PATH,
)


def get_keypair_name() -> str:
    return DEFAULT_KEY_PAIR_NAME


def get_admin_username() -> str:
    return DEFAULT_ADMIN_USERNAME


def get_admin_key_path() -> str:
    return DEFAULT_ADMIN_KEY_PATH
