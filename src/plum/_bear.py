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
    """Like :func:`is_bearable`, but decide parametrised user generics by intent.

    `Box[int](1)` and `Box[str]("a")` are both plain `Box` instances at runtime, so
    :func:`is_bearable` cannot tell them apart and every parametrisation matches
    equally. Python does record the intent: instantiating a subscripted generic sets
    `__orig_class__` on the instance once `__init__` returns. When the *hint* is a
    parametrised user generic, this decides by beartype's subtype ordering over that
    recorded type rather than by an instance check.

    A value without `__orig_class__` falls back to its runtime class. That is what
    makes `class IntBox(Box[int])` satisfy `Box[int]` — beartype reads
    `__orig_bases__` — while a bare `Box(1)`, which records no parameter, satisfies
    only the unparametrised `Box`.

    The hint decides whether this path is taken, never the value: a hint that is not
    a user generic is handed to :func:`is_bearable` unchanged, so faithful,
    `type[X]` and `Literal` matching is untouched.

    Variance is beartype's decision throughout; plum holds no opinion on it.

    Args:
        v (object): Value.
        t (object): Type hint.

    Returns:
        bool: Whether `v` matches `t`.
    """
    if _is_generic_hint(t):
        orig = getattr(v, "__orig_class__", None)
        if orig == t:
            # The commonest case by far: the value was instantiated at exactly this
            # parametrisation. Subtyping is reflexive, so answer without building a
            # single `TypeHint`.
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
