"""Infer `__orig_class__` for bare instantiations of a `typing.Generic` subclass."""

__all__ = ["generic"]

import functools
import typing
import warnings
from typing import Any, TypeVar

T = TypeVar("T")


def _can_carry_orig_class(cls: type, /) -> bool:
    """Check whether instances of `cls` can have an `__orig_class__` attribute.

    They can if they have a `__dict__` or if a class in the MRO declares the slot.
    """
    if cls.__dictoffset__:
        return True
    for base in cls.__mro__:
        slots = base.__dict__.get("__slots__")
        # `__slots__` may be a single string.
        if isinstance(slots, str):
            slots = (slots,)
        if slots is not None and "__orig_class__" in slots:
            return True
    return False


def generic(cls: type[T], /) -> type[T]:
    """Set `__orig_class__` on bare instantiations of a `typing.Generic` subclass.

    After decoration, `Box(1)` dispatches like `Box[T](1)`, where `T` is what
    `Box.__infer_type_parameter__(instance)` returns for the constructed instance: a
    type parameter, or a tuple of them for several parameters. Define it as a
    `classmethod`. An explicit subscript, as in `Box[str](1)`, still wins.

    If instances cannot carry `__orig_class__`, because `__slots__` omits it, or if
    `cls` cannot be subscripted by the inferred parameter, a `RuntimeWarning` is
    raised and the instance is left unparametrised.

    Args:
        cls (type): Class to decorate.

    Returns:
        type: `cls`, with its `__init__` wrapped.

    Example:
        >>> from typing import Generic, TypeVar
        >>> from plum import generic
        >>> T = TypeVar("T")

        >>> @generic
        ... class Box(Generic[T]):
        ...     def __init__(self, value):
        ...         self.value = value
        ...
        ...     @classmethod
        ...     def __infer_type_parameter__(cls, instance):
        ...         return type(instance.value)

        >>> Box(1).__orig_class__ == Box[int]
        True
    """
    if not issubclass(cls, typing.Generic):
        raise TypeError(
            f"`@generic` requires `{cls.__name__}` to be a `typing.Generic` "
            f"subclass, since it works by subscripting `type(self)`."
        )

    if not callable(getattr(cls, "__infer_type_parameter__", None)):
        raise TypeError(
            f"`@generic` requires `{cls.__name__}` to define "
            f"`__infer_type_parameter__` callable as "
            f"`{cls.__name__}.__infer_type_parameter__(instance)`, normally a "
            f"`classmethod`."
        )

    if not _can_carry_orig_class(cls):
        warnings.warn(
            f"`{cls.__name__}` defines `__slots__` without `'__orig_class__'`, so "
            f"its instances cannot carry that attribute and dispatch will not "
            f"route them to parametrised methods. Add `'__orig_class__'` to "
            f"`__slots__`.",
            RuntimeWarning,
            stacklevel=2,
        )

    original_init = cls.__init__

    @functools.wraps(original_init)
    def __init__(self: Any, *args: Any, **kw_args: Any) -> Any:
        # `mypyc` would otherwise infer `None` and refuse to return `result`.
        result: Any = original_init(self, *args, **kw_args)
        if result is not None:
            # Pass it on, so that Python raises as it would without the decorator.
            return result
        # Use `type(self)`, not `cls`: a subclass must infer its own class.
        actual = type(self)
        # A subclass such as `class IntBox(Box[int])` has nothing left to infer.
        if not actual.__parameters__:
            return None
        try:
            parameter = actual.__infer_type_parameter__(self)
            # `object.__setattr__` so that a frozen dataclass, or any class with a
            # custom `__setattr__`, still gets the attribute.
            object.__setattr__(self, "__orig_class__", actual[parameter])
        except (TypeError, AttributeError) as e:
            warnings.warn(
                f"`@generic` could not set `__orig_class__` on a "
                f"`{actual.__name__}` instance: {type(e).__name__}: {e}. Dispatch "
                f"will not route it to parametrised methods.",
                RuntimeWarning,
                stacklevel=2,
            )
        return None

    cls.__init__ = __init__  # type: ignore[method-assign]
    return cls
