__all__ = (
    "Callable",
    "TypeHint",
    "Missing",
    "Comparable",
    "wrap_lambda",
    "is_in_class",
    "get_class",
    "get_context",
    "argsort",
)

import abc
import sys
from collections.abc import Callable, Sequence
from typing import Any, TypeAlias, TypeVar

# We use this to indicate a reader that we expect a type hint. Using just
# `object` as a type hint is technically correct for `int | None` for example,
# but does not convey the intention to a reader. Furthermore, if later on,
# Python has a proper type for type hints, we can just replace it here.
TypeHint: TypeAlias = object
T = TypeVar("T")
R = TypeVar("R")  # Return type


class _MissingType(type):
    """The type of :class:`Missing`."""

    def __bool__(self) -> bool:
        # For some reason, Sphinx does attempt to evaluate `bool(Missing)`.
        # Let's try to keep Sphinx working correctly by not raising an
        # exception.
        if "sphinx" in sys.modules:
            return False

        raise TypeError("`Missing` has no boolean value.")


class Missing(metaclass=_MissingType):
    """A class that can be used to indicate that a value is missing. This class cannot
    be instantiated and has no boolean value."""

    def __init__(self) -> None:
        raise TypeError("`Missing` cannot be instantiated.")


class Comparable(metaclass=abc.ABCMeta):
    """A mixin that makes instances of the class comparable.

    Requires the subclass to just implement `__le__`.
    """

    def __eq__(self, other: object, /) -> bool:
        return self <= other <= self

    def __ne__(self, other: object, /) -> bool:
        return not self == other

    @abc.abstractmethod
    def __le__(self, other: object, /) -> bool:
        pass  # pragma: no cover

    def __lt__(self, other: object, /) -> bool:
        return self <= other and self != other

    def __ge__(self, other: object, /) -> bool:
        return other.__le__(self)  # type: ignore[no-any-return,operator]

    def __gt__(self, other: object, /) -> bool:
        return self >= other and self != other

    def is_comparable(self, other: object, /) -> bool:
        """Check whether this object is comparable with another one.

        Args:
            other (object): Object to check comparability with.

        Returns:
            Whether the object is comparable with `other`.
        """
        return self < other or self == other or self > other


def wrap_lambda(f: Callable[[T], R], /) -> Callable[[T], R]:
    """Wrap a callable in a lambda function.

    Args:
        f (Callable): Function to wrap.

    Returns:
        function: Wrapped version of `f`.
    """
    return lambda x: f(x)


def is_in_class(f: Callable[..., Any], /) -> bool:
    """Check if a function is part of a class.

    Args:
        f (function): Function to check.

    Returns:
        bool: Whether `f` is part of a class.
    """
    parts = f.__qualname__.split(".")
    return len(parts) >= 2 and parts[-2] != "<locals>"


def _split_parts(f: Callable[..., Any], /) -> list[str]:
    # Under edge cases, `f.__module__` can be `None`. In this case we, skip it.
    # Otherwise, the fully-qualified name is the name of the module plus the qualified
    # name of the function.
    module = (f.__module__ + ".") if f.__module__ else ""
    return (module + f.__qualname__).split(".")


def get_class(f: Callable[..., Any], /) -> str:
    """Assuming that `f` is part of a class, get the fully qualified name of the
    class.

    Args:
        f (function): Method to get class name for.

    Returns:
        str: Fully qualified name of class.
    """
    parts = _split_parts(f)
    return ".".join(parts[:-1])


def get_context(f: Callable[..., Any], /) -> str:
    """Get the fully qualified name of the context for `f`.

    If `f` is part of a class, then the context corresponds to the scope of the
    class.  If `f` is not part of a class, then the context corresponds to the
    scope of the function.

    Args:
        f (function): Method to get context for.

    Returns:
        str: The context of `f`.
    """
    parts = _split_parts(f)
    if is_in_class(f):
        # Split off function name and class.
        return ".".join(parts[:-2])
    else:
        # Split off function name only.
        return ".".join(parts[:-1])


def argsort(seq: Sequence[int], /) -> list[int]:
    """Compute the indices that sort an integer sequence.

    Args:
        seq (Sequence[int]): Sequence of integers to sort.

    Returns:
        list[int]: Indices that sort `seq`.
    """
    return sorted(range(len(seq)), key=seq.__getitem__)
