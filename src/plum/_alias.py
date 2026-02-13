"""This module monkey patches `__repr__` and `__str__` of `typing.Union` to control how
`typing.Unions` are displayed.

Example::

    >> plum.activate_union_aliases()

    >> IntOrFloat = typing.Union[int, float]

    >> IntOrFloat
    Union[int, float]

    >> plum.set_union_alias(IntOrFloat, "IntOrFloat")

    >> IntOrFloat
    typing.Union[IntOrFloat]

    >> typing.Union[int, float]
    typing.Union[IntOrFloat]

    >> typing.Union[int, float, str]
    typing.Union[IntOrFloat, str]

Note that `IntOrFloat` prints to `typing.Union[IntOrFloat]` rather than just
`IntOrFloat`. This is deliberate, with the goal of not breaking code that relies on
parsing how unions print.
"""

__all__ = (
    "activate_union_aliases",
    "deactivate_union_aliases",
    "set_union_alias",
)

import sys
from functools import wraps
from typing import Any, TypeVar, Union, _type_repr, get_args
from typing_extensions import TypeAliasType, deprecated

UnionT = TypeVar("UnionT")

_union_type = type(Union[int, float])  # noqa: UP007

if sys.version_info < (3, 14):  # pragma: specific no cover 3.14
    _original_repr = _union_type.__repr__
    _original_str = _union_type.__str__

    _ALIASED_UNIONS: dict[tuple[Any, ...], str] = {}

    @wraps(_original_repr)
    def _new_repr(self: object) -> str:
        """Print a `typing.Union`, replacing all aliased unions by their aliased names.

        Returns:
            str: Representation of a `typing.Union` taking into account union aliases.
        """
        args = get_args(self)
        args_set = set(args)

        # Find all aliased unions contained in this union.
        found_unions = []
        found_positions = []
        found_aliases = []
        for union, alias in reversed(_ALIASED_UNIONS.items()):
            union_set = set(union)
            if union_set <= args_set:
                found = False
                for i, arg in enumerate(args):
                    if arg in union_set:
                        found_unions.append(union_set)
                        found_positions.append(i)
                        found_aliases.append(alias)
                        found = True
                        break
                if not found:  # pragma: no cover
                    # This branch should never be reached.
                    raise AssertionError(
                        "Could not identify union. This should never happen."
                    )

        # Delete any unions that are contained in strictly bigger unions. We
        # check for strictly inequality because any union includes itself.
        for i in range(len(found_unions) - 1, -1, -1):
            for union_ in found_unions:
                if found_unions[i] < set(union_):
                    del found_unions[i]
                    del found_positions[i]
                    del found_aliases[i]
                    break

        # Create a set with all arguments of all found unions.
        found_args = set().union(*found_unions) if found_unions else set()

        # Build a mapping from original position to aliases to insert before it.
        inserts: dict[int, list[str]] = {}
        for pos, alias in zip(found_positions, found_aliases, strict=False):
            inserts.setdefault(pos, []).append(alias)
        # Interleave aliases at the appropriate positions.
        args = tuple(
            v for i, arg in enumerate(args) for v in (*inserts.pop(i, []), arg)
        )

        # Filter all elements of unions that are aliased.
        args = tuple(arg for arg in args if arg not in found_args)

        # Generate a string representation.
        args_repr = [a if isinstance(a, str) else _type_repr(a) for a in args]
        # Like `typing` does, print `Optional` whenever possible.
        if len(args) == 2:
            if args[0] is type(None):  # noqa: E721
                return f"typing.Optional[{args_repr[1]}]"
            elif args[1] is type(None):  # noqa: E721
                return f"typing.Optional[{args_repr[0]}]"
        # We would like to just print `args_repr[0]` whenever `len(args) == 1`, but
        # this might break code that parses how unions print.
        return "typing.Union[" + ", ".join(args_repr) + "]"

    @wraps(_original_str)
    def _new_str(self: object) -> str:
        """Does the same as :func:`_new_repr`.

        Returns:
            str: Representation of the `typing.Union` taking into account union aliases.
        """
        return _new_repr(self)

    @deprecated(
        "`activate_union_aliases` is deprecated and will be removed in a future version.",  # noqa: E501
        stacklevel=2,
    )
    def activate_union_aliases() -> None:
        """When printing `typing.Union`s, replace aliased unions by the aliased names.
        This monkey patches `__repr__` and `__str__` for `typing.Union`."""
        _union_type.__repr__ = _new_repr  # type: ignore[method-assign]
        _union_type.__str__ = _new_str  # type: ignore[method-assign]

    @deprecated(
        "`deactivate_union_aliases` is deprecated and will be removed in a future version.",  # noqa: E501
        stacklevel=2,
    )
    def deactivate_union_aliases() -> None:
        """Undo what :func:`.alias.activate` did. This restores the original  `__repr__`
        and `__str__` for `typing.Union`."""
        _union_type.__repr__ = _original_repr  # type: ignore[method-assign]
        _union_type.__str__ = _original_str  # type: ignore[method-assign]

    def set_union_alias(union: UnionT, alias: str) -> UnionT:
        """Change how a `typing.Union` is printed. This does not modify `union`.

        Args:
            union (type or type hint): A union.
            alias (str): How to print `union`.

        Returns:
            type or type hint: `union`.
        """
        args = get_args(union) if isinstance(union, _union_type) else (union,)
        for existing_union, existing_alias in _ALIASED_UNIONS.items():
            if set(existing_union) == set(args) and alias != existing_alias:
                if isinstance(union, _union_type):
                    union_str = _original_str(union)
                else:
                    union_str = repr(union)
                raise RuntimeError(
                    f"`{union_str}` already has alias `{existing_alias}`."
                )
        _ALIASED_UNIONS[args] = alias
        return union

else:  # pragma: specific no cover 3.13 3.12 3.11 3.10
    _ALIASED_UNIONS: dict[tuple[Any, ...], TypeAliasType] = {}

    @deprecated(
        "`activate_union_aliases` is deprecated and will be removed in a future version.",  # noqa: E501
        category=RuntimeWarning,
        stacklevel=2,
    )
    def activate_union_aliases() -> None:
        """When printing `typing.Union`s, replace aliased unions by the aliased names.
        This monkey patches `__repr__` and `__str__` for `typing.Union`."""

    @deprecated(
        "`deactivate_union_aliases` is deprecated and will be removed in a future version.",  # noqa: E501
        category=RuntimeWarning,
        stacklevel=2,
    )
    def deactivate_union_aliases() -> None:
        """Undo what :func:`.alias.activate` did. This restores the original  `__repr__`
        and `__str__` for `typing.Union`."""

    def set_union_alias(union: UnionT, /, alias: str) -> UnionT:
        """Register a union alias for use in plum's dispatch system.

        When used with plum's dispatch system, the union will be automatically
        transformed into a `TypeAliasType` during signature extraction, allowing
        dispatch to key off the alias name instead of the union structure.

        Args:
            union (type or type hint): A union type or a single type.
            alias (str): Alias name for the union.

        """
        # Handle both union types and single types, matching < 3.14 behaviour.
        args = get_args(union) if isinstance(union, _union_type) else (union,)

        # Check for conflicting aliases
        for existing_union, existing_alias in _ALIASED_UNIONS.items():
            if set(existing_union) == set(args) and alias != repr(existing_alias):
                union_str = repr(union)
                raise RuntimeError(
                    f"`{union_str}` already has alias `{existing_alias!r}`."
                )

        new_alias = TypeAliasType(alias, union, type_params=())  # type: ignore[misc]

        _ALIASED_UNIONS[args] = new_alias

        return union


def _transform_union_alias(x: object, /) -> object:
    """Transform a Union type hint to a TypeAliasType if it's registered in the alias
    registry. This is used by plum's dispatch machinery to use aliased names for unions.

    Args:
        x (type or type hint): Type hint, potentially a Union.

    Returns:
        type or type hint: If `x` is a Union registered in `_ALIASED_UNIONS`, returns
            the TypeAliasType. Otherwise returns `x` unchanged.
    """
    # TypeAliasType instances are already transformed, return as-is
    if isinstance(x, TypeAliasType):
        return x

    # Get the union args to check if it's registered
    args = get_args(x) if isinstance(x, _union_type) else None
    if args:
        args_set = set(args)
        # Look for a matching alias in the registry
        for union_args, type_alias in _ALIASED_UNIONS.items():
            if set(union_args) == args_set:
                return type_alias

    # Not a union or not aliased, return as-is
    return x
