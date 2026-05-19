"""Helpers for detecting and comparing parameterised generic type hints, and
the :func:`generic` decorator for auto-inferring ``__orig_class__``.

These utilities let the rest of plum treat ``list[int]``, ``dict[str, int]``,
and user-defined ``Box[int]`` consistently without plum making any variance
decisions of its own — that is deferred to :mod:`beartype.door`.
"""

__all__ = ("generic", "is_generic_hint", "le_generic")

import functools
import typing
import warnings
from collections.abc import Callable
from types import UnionType
from typing import Annotated, Any, TypeVar, get_args, get_origin, overload

from beartype.door import TypeHint
from beartype.typing import Protocol

# Special typing forms that look like parameterised generics but are NOT
# container types whose element types can be inferred from runtime values.
# We must exclude these so that `infer_hint`-based caching is never applied
# to value-constrained types like ``Annotated[int, Is[lambda x: x > 0]]``
# or to ``Union[int, str]``.
_EXCLUDED_ORIGINS: frozenset[object] = frozenset(
    {
        Annotated,  # Annotated[T, metadata...]
        typing.Union,  # Union[int, str], Optional[int]
        UnionType,  # int | str  (PEP 604 syntax)
    }
)


def is_generic_hint(t: object, /) -> bool:
    """Return ``True`` if *t* is a parameterised generic type hint.

    This covers:

    * Built-in parameterised forms: ``list[int]``, ``dict[str, int]``,
      ``tuple[int, str]``, ``set[float]``
    * :mod:`typing` / :mod:`collections.abc` generics: ``Sequence[int]``,
      ``Callable[[int], str]``
    * User-defined ``Generic`` subclasses: ``Box[int]``

    Plain (unsubscripted) types such as ``list``, ``Box``, or ``int`` return
    ``False``.

    Args:
        t: Object to inspect.

    Returns:
        ``True`` if *t* has a non-``None`` ``get_origin``, non-empty
        ``get_args``, and is not a special typing form like
        :data:`~typing.Annotated` or :data:`~typing.Union`.
    """
    origin = get_origin(t)
    return (
        origin is not None
        and isinstance(origin, type)
        and bool(get_args(t))
        and origin not in _EXCLUDED_ORIGINS
    )


def le_generic(left: object, right: object, /) -> bool:
    """Return ``True`` if *left* is a subtype of *right* according to beartype.

    Variance is entirely determined by :class:`beartype.door.TypeHint`; plum
    holds no opinion of its own for stdlib ``Generic`` types.

    Args:
        left: Left-hand type hint.
        right: Right-hand type hint.

    Returns:
        ``True`` if ``TypeHint(left) <= TypeHint(right)``.
    """
    return bool(TypeHint(left) <= TypeHint(right))


# ---------------------------------------------------------------------------
# @generic decorator
# ---------------------------------------------------------------------------


class HasInferTypeParameter(Protocol):  # type: ignore[misc]
    @classmethod
    def __infer_type_parameter__(cls, instance: object) -> object: ...


T = TypeVar("T", bound=HasInferTypeParameter)


@overload
def generic(cls: type[T]) -> type[T]: ...
@overload
def generic(cls: None = ...) -> Callable[[type[T]], type[T]]: ...
def generic(cls: type[T] | None = None, /) -> type[T] | Callable[[type[T]], type[T]]:  # type: ignore[misc]
    """Decorator that makes bare instantiation infer ``__orig_class__``.

    Apply to a :class:`typing.Generic` subclass.  After decoration, calling
    ``A(value)`` is equivalent to ``A[T](value)`` where ``T`` is the type
    returned by the class's ``__infer_type_parameter__`` classmethod.  This
    enables plum dispatch to route bare instances to parameterised overloads
    without requiring an explicit ``A[Any]`` fallback.

    The class **must** define ``__infer_type_parameter__`` as a
    :func:`classmethod` that accepts the freshly-constructed instance and
    returns the type parameter (or a tuple of type parameters for multi-
    parameter generics).  The decorator raises :exc:`TypeError` at decoration
    time if the method is absent.

    Subscripted construction (e.g. ``A[str](value)``) still wins: Python sets
    ``__orig_class__`` *after* ``__init__`` returns, overwriting whatever the
    wrapper inferred.

    Examples::

        from typing import Generic, TypeVar
        from plum import dispatch, generic

        T = TypeVar("T")


        @generic
        class Box(Generic[T]):
            def __init__(self, value: T) -> None:
                self.value = value

            @classmethod
            def __infer_type_parameter__(cls, instance):
                return type(instance.value)


        @dispatch
        def unwrap(b: Box[int]) -> str:
            return "int box"


        @dispatch
        def unwrap(b: Box[str]) -> str:
            return "str box"


        unwrap(Box(1))  # → "int box"   (inferred Box[int])
        unwrap(Box("hello"))  # → "str box"   (inferred Box[str])
    """
    if cls is None:
        # Support @generic() with parentheses.
        return generic

    if not hasattr(cls, "__infer_type_parameter__"):
        raise TypeError(
            f"@generic requires {cls.__name__} to define "
            "__infer_type_parameter__(cls, instance) as a classmethod."
        )

    # Warn at decoration time if the class declares __slots__ without
    # '__orig_class__'.  Without this slot instances cannot carry the attribute
    # and dispatch will silently fail to route them.
    if (
        "__slots__" in cls.__dict__
        and "__orig_class__" not in cls.__dict__["__slots__"]
    ):
        warnings.warn(
            f"@generic: {cls.__name__} defines __slots__ without "
            "'__orig_class__'. Instances will not carry __orig_class__ "
            "and plum dispatch will not be able to route them to "
            "parameterised overloads. Add '__orig_class__' to __slots__.",
            RuntimeWarning,
            stacklevel=2,
        )

    orig_init = cls.__init__

    @functools.wraps(orig_init)
    def __init__(self: T, *args: Any, **kwargs: Any) -> None:
        orig_init(self, *args, **kwargs)
        actual_cls = type(self)
        try:
            params = actual_cls.__infer_type_parameter__(self)
            # Use object.__setattr__ to bypass frozen-dataclass __setattr__ and
            # any other custom __setattr__ that would reject the write.
            # AttributeError is caught below for slotted classes that do not
            # include '__orig_class__' in __slots__.
            object.__setattr__(self, "__orig_class__", actual_cls[params])  # type: ignore[index]
        except (TypeError, AttributeError) as e:
            warnings.warn(
                f"@generic: could not set __orig_class__ on {actual_cls.__name__} "
                f"instance — {type(e).__name__}: {e}. "
                "Plum dispatch will not be able to route this instance to "
                "parameterised overloads.",
                RuntimeWarning,
                stacklevel=2,
            )

    cls.__init__ = __init__  # type: ignore[method-assign,assignment]
    return cls
