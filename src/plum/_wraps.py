"""Faster, narrower replacements for :func:`functools.wraps`.

About 2.5x faster, in the compiled wheels too, since `mypyc` calls into the interpreted
stdlib for `functools.wraps`. TODO: delete this module once that is no longer the case.
"""

__all__ = ("update_wrapper", "update_wrapper_names")

from collections.abc import Callable
from functools import WRAPPER_ASSIGNMENTS
from typing import Any, Protocol

_HAS_ANNOTATE = "__annotate__" in WRAPPER_ASSIGNMENTS
"""`__annotate__` (3.14+) or `__annotations__`: whichever `functools.wraps` copies."""


class _Wrappable(Protocol):
    __name__: str
    __qualname__: str
    __wrapped__: Callable[..., Any]


def _generate_qualname(f: Callable[..., Any], /) -> str:
    """Generate a qualified name for a function.

    This function can be interpreted as an improved version of `f.__qualname__`
    and can be run regardless of whether `f.__qualname__` exists.

    Args:
        f (Callable): Function.

    Returns:
        str: Qualified name.
    """
    qualname = getattr(f, "__qualname__", f.__name__)

    # TODO: If we ever want to scope functions, we can uncomment this.
    # if hasattr(f, "__module__"):
    #     qualname = f"{f.__module__}.{qualname}"
    # `__main__` would be part of `f.__name__` in e.g. the REPL.
    # qualname = qualname.replace("__main__.", """)

    return qualname


def update_wrapper_names(wrapper: _Wrappable, wrapped: Callable[..., Any], /) -> None:
    """Copy `wrapped`'s `__name__`, `__qualname__` and `__wrapped__` onto `wrapper`.

    For `Function` and `_BoundFunction`, which serve `__doc__` and `__module__` through
    non-data descriptors that an instance attribute would shadow. Use
    :func:`update_wrapper` for anything else.
    """
    wrapper.__name__ = wrapped.__name__
    wrapper.__qualname__ = _generate_qualname(wrapped)
    wrapper.__wrapped__ = wrapped


def update_wrapper(wrapper: Any, wrapped: Callable[..., Any], /) -> None:
    """Copy `wrapped`'s metadata onto `wrapper`, like :func:`functools.wraps`.

    Two differences: `__type_params__` is not copied, since nothing reads it back off a
    wrapper, and a missing `__qualname__` falls back to `__name__`.

    Args:
        wrapper (object): Object to copy metadata onto.
        wrapped (Callable): Function to copy metadata from.
    """
    wrapper.__module__ = wrapped.__module__
    wrapper.__name__ = wrapped.__name__
    wrapper.__qualname__ = _generate_qualname(wrapped)
    wrapper.__doc__ = wrapped.__doc__
    try:
        if _HAS_ANNOTATE:
            # `mypy` flags `__annotate__` below 3.14 and an unused ignore above it.
            wrapper.__annotate__ = wrapped.__annotate__  # type: ignore[attr-defined, unused-ignore]
        else:
            wrapper.__annotations__ = wrapped.__annotations__
    except AttributeError:
        # A callable object need not have annotations.
        pass
    # A slotted `wrapped` has no `__dict__`. The merge comes before `__wrapped__`, as in
    # `functools.wraps`, so a `__wrapped__` in `wrapped.__dict__` cannot win.
    wrapper.__dict__.update(getattr(wrapped, "__dict__", {}))
    wrapper.__wrapped__ = wrapped
