from functools import wraps
from typing import Callable

_sentinel = object()


def run_once(func: Callable) -> Callable:
    """
    Decorator that creates a function that is restricted to execute `func` once. Repeated calls to the function will
    return the value of the first call.

    :param func: The decorated function
    """
    result = _sentinel

    @wraps(func)
    def func_run_once(*args, **kwargs):
        nonlocal result

        if result is _sentinel:
            result = func(*args, **kwargs)

        return result

    return func_run_once
