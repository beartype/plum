from typing import Callable, TypeVar, overload

from plum import Function

__all__ = ["overload", "dispatch"]

T = TypeVar("T", bound=Callable)

def dispatch(f: Callable) -> Function: ...
