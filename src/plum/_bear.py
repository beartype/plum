__all__ = ["is_bearable"]

from functools import partial
from typing import Annotated, get_args, get_origin

from beartype import (
    BeartypeConf as _BeartypeConf,
    BeartypeStrategy as _BeartypeStrategy,
)
from beartype.door import TypeHint as _TypeHint, is_bearable as _is_bearable

from ._type import UNION_TYPES, _is_generic_hint

# Ensure that type checking is always entirely correct! The default O(1) strategy
# is super fast, but might yield unpredictable dispatch behaviour. The O(n) strategy
# actually is not yet available, but we can already opt in to use it.
is_bearable = partial(_is_bearable, conf=_BeartypeConf(strategy=_BeartypeStrategy.On))


def is_bearable_with_orig(v: object, t: object, /) -> bool:
    """Like :func:`is_bearable`, but match user generics by `__orig_class__`.

    `Box[int](1)` and `Box[str]("a")` are both plain `Box` instances, so
    :func:`is_bearable` cannot tell them apart. Python does record the
    parametrisation on the instance as `__orig_class__`, so, for a parametrised user
    generic `t`, check whether that is a subhint of `t`. A value without
    `__orig_class__`, like `Box(1)` or an instance of `class IntBox(Box[int])`, is
    checked by its type instead. Unions and `Annotated` are checked member by member,
    and any other hint is passed to :func:`is_bearable`.

    Args:
        v (object): Value.
        t (object): Type hint.

    Returns:
        bool: Whether `v` matches `t`.
    """
    if _is_generic_hint(t):
        orig = getattr(v, "__orig_class__", None)
        if orig == t:
            # The common case. Avoid building `TypeHint`s.
            return True
        return bool(_TypeHint(type(v) if orig is None else orig) <= _TypeHint(t))

    origin = get_origin(t)
    if origin in UNION_TYPES:
        # A union is matched precisely if one of its members is.
        return any(is_bearable_with_orig(v, arg) for arg in get_args(t))
    if origin is Annotated:
        # The metadata can only reject further, so let the recursion decide the
        # underlying hint and let `is_bearable` apply the validators.
        return is_bearable_with_orig(v, get_args(t)[0]) and bool(is_bearable(v, t))

    return bool(is_bearable(v, t))
