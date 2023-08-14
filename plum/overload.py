from typing import Callable, TypeVar

try:
    from typing_extensions import get_overloads, overload
except ImportError:
    raise RuntimeError(
        "To use `plum.overload`, `typing-extensions` must be installed. "
        "Please run `pip install typing-extensions."
    )

from .function import Function

__all__ = ["overload", "dispatch"]

T = TypeVar("T", bound=Callable)


def dispatch(f: T) -> T:
    """Decorator to register a particular signature."""
    f_plum = Function(f)
    for method in get_overloads(f):
        f_plum.dispatch(method)
    return f_plum
