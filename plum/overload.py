from typing import Callable, TypeVar

from typing_extensions import get_overloads, overload

from .function import Function

__all__ = ["overload", "dispatch"]

T = TypeVar("T", bound=Callable)


def dispatch(f: T) -> T:
    """Decorator to register a particular signature."""
    f_plum = Function(f)
    for method in get_overloads(f):
        f_plum.dispatch(method)
    return f_plum
