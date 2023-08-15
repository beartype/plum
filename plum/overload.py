import sys
from typing import Callable, TypeVar

if sys.version_info >= (3, 11):  # pragma: specific no cover 3.7 3.8 3.9 3.10
    from typing import get_overloads, overload
else:  # pragma: specific no cover 3.11
    from typing_extensions import get_overloads, overload

from .function import Function

__all__ = ["overload", "dispatch"]

T = TypeVar("T", bound=Callable[..., Any])


def dispatch(f: Callable) -> Function:
    """Decorator to register a particular signature."""
    f_plum = Function(f)
    for method in get_overloads(f):
        f_plum.dispatch(method)
    return f_plum
