import hashlib
from typing import Optional


def generate_lb_name(cluster_name: str, tg_name: Optional[str] = None) -> str:
    cluster_name_cleaned = cluster_name.replace("-", "")
    cluster_name_hash = hashlib.md5(cluster_name_cleaned.encode("utf-8")).hexdigest()[:4]
    return f"{cluster_name_cleaned[:6]}{cluster_name_hash}{'-' + tg_name if tg_name else ''}"
