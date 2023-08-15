from typing import Any, Callable, TypeVar, overload

from plum import Function

__all__ = ["overload", "dispatch"]

T = TypeVar("T", bound=Callable[..., Any])

def dispatch(f: Callable) -> Function: ...
