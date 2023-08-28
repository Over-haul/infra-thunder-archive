from ..config import get_sysenv

PARAMETER_STORE_BASE = "/Infrastructure"
PARAMETER_STORE_COMMON = f"{PARAMETER_STORE_BASE}/{get_sysenv()}/common"
