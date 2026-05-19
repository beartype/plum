"""Helpers for detecting and comparing parameterised generic type hints.

These utilities let the rest of plum treat ``list[int]``, ``dict[str, int]``,
and user-defined ``Box[int]`` consistently without plum making any variance
decisions of its own — that is deferred to :mod:`beartype.door`.
"""

__all__ = ("is_generic_hint", "le_generic")

import typing
from typing import Annotated, get_args, get_origin

from beartype.door import TypeHint

# Special typing forms that look like parameterised generics but are NOT
# container types whose element types can be inferred from runtime values.
# We must exclude these so that `infer_hint`-based caching is never applied
# to value-constrained types like ``Annotated[int, Is[lambda x: x > 0]]``
# or to ``Union[int, str]``.
_EXCLUDED_ORIGINS: frozenset[object] = frozenset(
    {
        Annotated,  # Annotated[T, metadata...]
        typing.Union,  # Union[int, str], Optional[int]
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
    return origin is not None and bool(get_args(t)) and origin not in _EXCLUDED_ORIGINS


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
