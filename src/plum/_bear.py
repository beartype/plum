__all__ = ["is_bearable", "is_bearable_with_orig"]

from functools import partial
from typing import Any

from beartype import (
    BeartypeConf as _BeartypeConf,
    BeartypeStrategy as _BeartypeStrategy,
)
from beartype.door import TypeHint as _TypeHint, is_bearable as _is_bearable

# Ensure that type checking is always entirely correct! The default O(1)
# strategy is super fast, but might yield unpredictable dispatch behaviour. We
# opt into the slower O(n) strategy to ensure that dispatch is always correct.
is_bearable = partial(_is_bearable, conf=_BeartypeConf(strategy=_BeartypeStrategy.On))


def is_bearable_with_orig(value: object, hint: Any, /) -> bool:
    """Like :func:`is_bearable`, but honours ``__orig_class__`` on *value*.

    When a user instantiates a subscripted generic via ``Box[int](1)``, Python
    sets ``instance.__orig_class__ = Box[int]`` after ``__init__`` returns.
    :func:`beartype.door.is_bearable` does **not** inspect this attribute, so it
    cannot distinguish ``Box[int](1)`` from ``Box[str](1)``.

    This function detects the presence of ``__orig_class__`` and, when found,
    checks membership using :class:`beartype.door.TypeHint` subtype ordering
    (``orig_class <= hint``) rather than instance inspection.  This makes
    ``is_bearable_with_orig(Box[int](1), Box[str])`` return ``False`` while
    keeping ``is_bearable_with_orig(Box[int](1), Box)`` as ``True``.

    For values without ``__orig_class__`` the call is forwarded unchanged to
    :func:`is_bearable`.
    """
    orig = getattr(value, "__orig_class__", None)
    if orig is not None:
        # Fast path: exact match avoids TypeHint construction entirely.
        if orig == hint:
            return True
        return bool(_TypeHint(orig) <= _TypeHint(hint))
    return is_bearable(value, hint)
