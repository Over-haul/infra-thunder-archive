def kebab_from_snake(v: str) -> str:
    """Convert string from snake to kebab case

    :param v: String in snake case
    :return: String in kebab case
    """
    return "-".join(v.split("_"))
