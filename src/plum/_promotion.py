"""Promotion and conversion functions."""

__all__ = [
    "convert",
    "add_conversion_method",
    "conversion_method",
    "add_promotion_rule",
    "promote",
]

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypeVar

from beartype.door import TypeHint

import plum._function
from ._bear import is_bearable
from ._dispatcher import Dispatcher
from ._type import is_faithful, resolve_type_hint
from .repr import repr_short

T = TypeVar("T")
R = TypeVar("R")

if TYPE_CHECKING:
    TypeTo = TypeVar("TypeTo")
    typeTypeTo: TypeAlias = type[TypeTo]
else:
    TypeTo = Any
    typeTypeTo = Any

_dispatch = Dispatcher()

_IDENTITY_CONVERSION_LIMIT = 4096
"""Maximum number of entries in :obj:`plum._function.identity_conversions`.

An entry is built from a return annotation and an argument's type, both of which come
from the program's source rather than its data, so the natural size is the number of
`(argument type, return annotation)` pairs ever returned through. The limit is a
ceiling for the pathological case only: once it is reached, further pairs simply take
the full conversion path, exactly as they did before this cache existed.

The policy lives here rather than beside the set because this module decides what is
memoisable; `_function` only stores the answer and reads it on the hot path."""


@_dispatch
def convert(obj: object, type_to: typeTypeTo) -> TypeTo:
    """Convert an object to a particular type.

    Args:
        obj (object): Object to convert.
        type_to (type): Type to convert to.

    Returns:
        object: `obj` converted to type `type_to`.
    """
    # TODO: Can we implement this without using `type`?!
    type_from = type(obj)
    cache = plum._function.identity_conversions
    # `type_to` is keyed unresolved because that is what the hot path holds, and it is
    # looked up before resolving so that a known pair costs a single lookup. An
    # unhashable `type_to` raises `TypeError` here, as it already did further down when
    # the conversion method was looked up.
    known: bool | None = cache.get((type_from, type_to))
    if known:
        return obj

    resolved = resolve_type_hint(type_to)
    # Resolve and call the conversion method directly rather than through
    # `_convert.invoke`, which builds a wrapper object on every call.
    method, return_type = _convert._resolve_method_with_cache(
        types=(type_from, resolved)
    )
    result = plum._function._convert(method(obj, resolved), return_type)

    # Record what conversion did for this pair, so that `plum._function._convert` can
    # skip straight to the result next time -- and so that the analysis below, which
    # walks the annotation, runs once per pair rather than once per call. Two
    # conditions make the outcome a property of `(type_from, type_to)` alone rather
    # than of `obj`:
    #
    #   * `method is _identity_conversion`, i.e. no conversion method applied and the
    #     fallback returned `obj` unchanged. A conversion method may be registered
    #     later, which is why `add_conversion_method` clears the cache.
    #   * `is_faithful(resolved)`, which is *defined* as
    #     `isinstance(x, t) == issubclass(type(x), t)`, so the fallback's check depends
    #     only on `type_from`. Without it the check can depend on the value (a
    #     `Literal`, a type with a custom `__instancecheck__`) and must be re-run.
    #
    # A raising call never reaches here, so a recorded `True` is always a conversion
    # that succeeded and returned `obj` itself.
    if known is None and len(cache) < _IDENTITY_CONVERSION_LIMIT:
        cache[type_from, type_to] = method is _identity_conversion and is_faithful(
            resolved
        )

    return result


# Deliver `convert`.
plum._function._promised_convert = convert


def _identity_conversion(obj, type_to):  # type: ignore[no-untyped-def]
    """Fallback conversion: check the type and return `obj` unchanged.

    Bound to a module-level name so that :func:`convert` can recognise it by identity
    and conclude that no conversion method applied.
    """
    if not is_bearable(obj, resolve_type_hint(type_to)):
        raise TypeError(f"Cannot convert `{obj}` to `{repr_short(type_to)}`.")
    return obj


_convert = _dispatch(_identity_conversion)


class _ConversionCallable(Protocol[T, R]):
    def __call__(self, obj: T) -> R: ...


def add_conversion_method(
    type_from: type[T],
    type_to: type[R],
    f: _ConversionCallable[T, R],
) -> None:
    """Add a conversion method to convert an object from one type to another.

    Args:
        type_from (type): Type to convert from.
        type_to (type): Type to convert to.
        f (function): Function that converts an object of type `type_from` to
            type `type_to`.
    """

    @_convert.dispatch
    def perform_conversion(obj: type_from, _: type_to):
        return f(obj)

    # A pair previously recorded as an identity conversion may now be handled by this
    # method: `type_from` can be a subclass of a `type_to` that an earlier call proved
    # convertible only by the fallback. The cache is a pure optimisation, so dropping
    # all of it is both correct and cheap -- conversion methods are registered rarely.
    plum._function._clear_identity_conversions()


def conversion_method(
    type_from: type[T], type_to: type[R]
) -> Callable[[_ConversionCallable[T, R]], _ConversionCallable[T, R]]:
    """Decorator to add a conversion method to convert an object from one
    type to another.

    Args:
        type_from (type): Type to convert from.
        type_to (type): Type to convert to.
    """

    def add_method(f: _ConversionCallable[T, R]) -> _ConversionCallable[T, R]:
        add_conversion_method(type_from, type_to, f)
        return f

    return add_method


# Add some common conversion methods.
add_conversion_method(object, tuple, lambda x: (x,))
add_conversion_method(tuple, tuple, lambda x: x)
add_conversion_method(list, tuple, tuple)
add_conversion_method(object, list, lambda x: [x])
add_conversion_method(list, list, lambda x: x)
add_conversion_method(tuple, list, list)
add_conversion_method(bytes, str, lambda x: x.decode("utf-8", "replace"))


@_dispatch
def _promotion_rule(type1, type2):  # type: ignore[no-untyped-def]
    """Promotion rule.

    Args:
        type1 (type): First type to promote.
        type2 (type): Second type to promote.

    Returns:
        type: Type to convert to.
    """
    type1 = resolve_type_hint(type1)
    type2 = resolve_type_hint(type2)
    if TypeHint(type1) <= TypeHint(type2):
        return type2
    elif TypeHint(type2) <= TypeHint(type1):
        return type1
    else:
        raise TypeError(
            f"No promotion rule for `{repr_short(type1)}` and `{repr_short(type2)}`."
        )


@_dispatch
def add_promotion_rule(type1: object, type2: object, type_to: object) -> None:
    """Add a promotion rule.

    Args:
        type1 (type): First type to promote.
        type2 (type): Second type to promote.
        type_to (type): Type to convert to.
    """

    @_promotion_rule.dispatch
    def rule(t1: type1, t2: type2):
        return type_to

    # If the types are the same, we don't need to add the reverse rule. Resolve the
    # types to handle the case where types are equal, but not identical.
    if TypeHint(resolve_type_hint(type1)) == TypeHint(resolve_type_hint(type2)):
        return  # Escape early.

    @_promotion_rule.dispatch
    def rule(t1: type2, t2: type1):  # noqa: F811
        return type_to


@_dispatch
def promote(obj1, obj2, *objs):
    """Promote objects to a common type.

    Args:
        \\*objs (object): Objects to convert.

    Returns:
        tuple: `objs`, but all converted to a common type.
    """
    # Convert to a single tuple.
    objs = (obj1, obj2) + objs

    # Get the types of the objects.
    # TODO: Can we implement this without calling `type`?!
    types = [type(obj) for obj in objs]

    def _promote_types(t0, t1):
        return resolve_type_hint(_promotion_rule.invoke(t0, t1)(t0, t1))

    # Find the common type.
    _promotion_rule._resolve_pending_registrations()
    common_type = _promote_types(types[0], types[1])
    for t in types[2:]:
        common_type = _promote_types(common_type, t)

    # Convert objects and return.
    return tuple(convert(obj, common_type) for obj in objs)


@_dispatch
def promote(obj: object):  # noqa: F811
    # Promote should always return a tuple to avoid edge cases.
    return (obj,)


@_dispatch
def promote():  # noqa: F811
    return ()
