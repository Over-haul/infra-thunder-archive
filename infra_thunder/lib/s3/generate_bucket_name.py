import hashlib

from ..config import get_sysenv, get_purpose, get_phase


def generate_bucket_name(name: str) -> str:
    sysenv_hash = hashlib.md5(get_sysenv().encode("utf-8")).hexdigest()
    return f"{get_purpose()}-{get_phase()}-{sysenv_hash[-5:]}-{name}"
