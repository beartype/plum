from typing import Callable, TypeVar, overload

__all__ = ["overload", "dispatch"]

T = TypeVar("T", bound=Callable)

def dispatch(f: T) -> T: ...
