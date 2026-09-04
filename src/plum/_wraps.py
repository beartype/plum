"""A faster :func:`functools.wraps` for the wrappers plum builds per `invoke`.

Trivial, but about 2.5x faster than the stdlib: ~0.43 us against ~1.1 us.

TODO: check in on `mypyc` now and then. It compiles `functools.wraps` as a plain call
into the interpreted stdlib, so the gap above holds in the compiled wheels too. Once
`mypyc` gains native support for `functools.wraps` (or otherwise makes it comparably
cheap), benchmark it against :func:`_wraps` and, if the gap is gone, delete this module
in favour of `functools.wraps`.
"""

from collections.abc import Callable
from functools import WRAPPER_ASSIGNMENTS
from typing import Any

_HAS_ANNOTATE = "__annotate__" in WRAPPER_ASSIGNMENTS
"""`__annotate__` (3.14+) or `__annotations__`: whichever `functools.wraps` copies."""


def _wraps(wrapper: Any, wrapped: Callable[..., Any], /) -> None:
    """Copy `wrapped`'s metadata onto `wrapper`, like :func:`functools.wraps`.

    Copies the same names, straight-line, except `__type_params__`, which nothing reads
    back off a wrapper. Annotations stay lazy on 3.14 (see :data:`_HAS_ANNOTATE`).
    :func:`plum._function._wraps_native` is the cut-down form for `Function`.

    Args:
        wrapper (object): Object to copy metadata onto.
        wrapped (Callable): Function to copy metadata from.
    """
    wrapper.__module__ = wrapped.__module__
    wrapper.__name__ = wrapped.__name__
    try:
        # A callable object need not have `__qualname__`.
        wrapper.__qualname__ = wrapped.__qualname__
    except AttributeError:
        wrapper.__qualname__ = wrapped.__name__
    wrapper.__doc__ = wrapped.__doc__
    try:
        if _HAS_ANNOTATE:
            # `unused-ignore` as well: `__annotate__` exists only from Python 3.14,
            # so `mypy` flags the attribute below 3.14 and flags the ignore above it.
            wrapper.__annotate__ = wrapped.__annotate__  # type: ignore[attr-defined, unused-ignore]
        else:
            wrapper.__annotations__ = wrapped.__annotations__
    except AttributeError:
        # A callable object need not carry annotations at all.
        pass
    # Last, as `functools.wraps` does, so `wrapped.__dict__["__wrapped__"]` can't win.
    # Only the read is guarded: a slotted `wrapped` is fine, a slotted `wrapper` a bug.
    try:
        attrs = wrapped.__dict__
    except AttributeError:
        pass
    else:
        wrapper.__dict__.update(attrs)
    wrapper.__wrapped__ = wrapped
