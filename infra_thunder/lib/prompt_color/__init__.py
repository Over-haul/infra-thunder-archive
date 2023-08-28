from infra_thunder.lib.config import thunder_env

DEFAULT_PROMPT_COLOR = "green"


def get_prompt_color() -> str:
    return thunder_env.get("prompt_color", DEFAULT_PROMPT_COLOR)
