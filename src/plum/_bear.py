__all__ = ["is_bearable", "is_bearable_with_orig"]

from functools import partial
from typing import Any, Generic, get_args, get_origin

from beartype import (
    BeartypeConf as _BeartypeConf,
    BeartypeStrategy as _BeartypeStrategy,
)
from beartype.door import TypeHint as _TypeHint, is_bearable as _is_bearable

# Ensure that type checking is always entirely correct! The default O(1)
# strategy is super fast, but might yield unpredictable dispatch behaviour. We
# opt into the slower O(n) strategy to ensure that dispatch is always correct.
is_bearable = partial(_is_bearable, conf=_BeartypeConf(strategy=_BeartypeStrategy.On))


def _is_user_generic_origin(origin: object) -> bool:
    """Return True iff *origin* is a user-defined ``Generic[T]`` subclass.

    Built-in generics (``list``, ``dict``, ``tuple``, etc.) return False because
    beartype can introspect them directly.  Custom ``class Box(Generic[T])``
    subclasses return True because beartype cannot verify ``T`` at runtime.
    """
    return isinstance(origin, type) and Generic in origin.__mro__


def is_bearable_with_orig(value: object, hint: Any, /) -> bool:
    """Like :func:`is_bearable`, but honours ``__orig_class__`` on *value*.

    When a user instantiates a subscripted generic via ``Box[int](1)``, Python
    sets ``instance.__orig_class__ = Box[int]`` after ``__init__`` returns.
    :func:`beartype.door.is_bearable` does **not** inspect this attribute, so it
    cannot distinguish ``Box[int](1)`` from ``Box[str](1)``.

    This function adds two behaviours on top of :func:`is_bearable`:

    1. **``__orig_class__`` present.**  Membership is checked using
       :class:`beartype.door.TypeHint` subtype ordering (``orig_class <=
       hint``).  ``is_bearable_with_orig(Box[int](1), Box[str])`` returns
       ``False``; ``is_bearable_with_orig(Box[int](1), Box)`` returns ``True``.

    2. **``__orig_class__`` absent and *hint* is a parameterized user-defined
       Generic.**  In this case beartype cannot verify the type parameter, so to
       keep dispatch unambiguous we treat such hints as *non-matching* —
       **except** when every parameter is :data:`typing.Any`, which acts as the
       explicit "no parameterization information available" fallback overload.
       So ``is_bearable_with_orig(Box(1), Box[int])`` returns ``False`` while
       ``is_bearable_with_orig(Box(1), Box[Any])`` returns ``True``.

    For all other cases the call is forwarded unchanged to :func:`is_bearable`.
    """
    orig = getattr(value, "__orig_class__", None)
    if orig is not None:
        # Fast path: exact match avoids TypeHint construction entirely.
        if orig == hint:
            return True
        return bool(_TypeHint(orig) <= _TypeHint(hint))

    # No __orig_class__: special-case parameterized user-defined generics so
    # they don't all collapse into "matches everything".  This is what makes
    # `A[Any]` a useful explicit fallback for bare `A(1)` instances.
    origin = get_origin(hint)
    if origin is not None and _is_user_generic_origin(origin):
        args = get_args(hint)
        if args and all(a is Any for a in args):
            return isinstance(value, origin)
        return False

    return is_bearable(value, hint)  # type: ignore[no-any-return]
