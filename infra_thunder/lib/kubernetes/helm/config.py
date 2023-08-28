from dataclasses import dataclass
from typing import Any, Optional, Callable


@dataclass
class HelmChart:
    # TODO: more helm chart goodness
    chart: str
    namespace: str
    repo: str
    version: str
    values: dict[Any, Any]
    skip_crd_rendering: bool = False
    transformations: Optional[list[Callable]] = None
