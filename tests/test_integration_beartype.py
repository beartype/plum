"""End-to-end tests for the `beartype` behaviour that Plum's resolver depends on.

`tests/test_type.py` pins the `Any` handling at the level of `_type_hint_eq` and
`_type_hint_le`, and `tests/test_resolver.py` pins it for a two-method `Resolver`.
These tests instead exercise the whole public path - `@dispatch`, signature
registration, method resolution, and the call cache - for the overload shape that
broke in the wild: a set of concrete types with a single `Any` fallback.
"""

import typing
from numbers import Number
from typing import Any

import pytest

from beartype.door import TypeHint

import plum


def test_any_fallback_in_large_overload_set(dispatch: plum.Dispatcher):
    """Regression test for https://github.com/beartype/plum/issues/295.

    An `Any` fallback must register as its own method next to every concrete type in
    the set, and must only ever be selected for arguments that match nothing else.
    When `Any` compares equal to the concrete types, all of these overloads collapse
    onto one another and registration fails with an `AssertionError` from the
    resolver. Taken from `netket.utils.numbers`, which this broke.
    """

    @dispatch
    def f(x: Number):
        return "Number"

    @dispatch
    def f(x: list):
        return "list"

    @dispatch
    def f(x: None):
        return "None"

    @dispatch
    def f(x: type):
        return "type"

    @dispatch
    def f(x: Any):
        return "Any"

    # Every concrete overload must survive alongside the fallback.
    assert len(f.methods) == 5

    assert f(1) == "Number"
    assert f(1.0) == "Number"
    assert f([1]) == "list"
    assert f(None) == "None"
    assert f(int) == "type"

    # The fallback is reached only by arguments that match nothing else.
    assert f("x") == "Any"
    assert f({1: 2}) == "Any"

    # Dispatch is cached after the first call, so resolve everything twice.
    assert f(1) == "Number"
    assert f("x") == "Any"


def test_any_fallback_with_unannotated_parameter(dispatch: plum.Dispatcher):
    """An unannotated parameter resolves to `Any` and must behave as the fallback."""

    @dispatch
    def f(x: int):
        return "int"

    @dispatch
    def f(x):
        return "fallback"

    assert len(f.methods) == 2
    assert f(1) == "int"
    assert f("x") == "fallback"


def test_nested_any_fallback_in_overload_set(dispatch: plum.Dispatcher):
    """The same must hold for an `Any` nested inside a parameterised hint."""

    @dispatch
    def f(x: list[int]):
        return "list[int]"

    @dispatch
    def f(x: list[str]):
        return "list[str]"

    @dispatch
    def f(x: list[Any]):
        return "list[Any]"

    assert len(f.methods) == 3
    assert f([1]) == "list[int]"
    assert f(["a"]) == "list[str]"
    assert f([1.0]) == "list[Any]"


def test_any_fallback_on_multiple_parameters(dispatch: plum.Dispatcher):
    """`Any` must stay the least specific type in every argument position."""

    @dispatch
    def f(x: int, y: int):
        return "int, int"

    @dispatch
    def f(x: int, y: Any):
        return "int, Any"

    @dispatch
    def f(x: Any, y: Any):
        return "Any, Any"

    assert len(f.methods) == 3
    assert f(1, 1) == "int, int"
    assert f(1, "y") == "int, Any"
    assert f("x", "y") == "Any, Any"


@pytest.mark.parametrize("hint", [int, Number, list, list[int], str, type(None)])
def test_beartype_typehint_equality_is_symmetric(hint):
    """Plum relies on this contract from `beartype`.

    Plum considers two signatures identical when each is a subhint of the other, so
    an asymmetric `__eq__` on `TypeHint` makes "identical" depend on registration
    order and silently drops methods. `Any` against a concrete type is the case that
    regressed; see https://github.com/beartype/beartype/issues/682.
    """
    assert (TypeHint(Any) == TypeHint(hint)) == (TypeHint(hint) == TypeHint(Any))
    assert (TypeHint(int) == TypeHint(hint)) == (TypeHint(hint) == TypeHint(int))


@pytest.mark.parametrize("hint", [Any, int, Number, list[int], str])
def test_beartype_typehint_equality_agrees_with_hash(hint):
    """Plum relies on this contract from `beartype`.

    Plum keys its signature bookkeeping on `TypeHint`, so wrappers that compare equal
    must hash equally. A wrapper that is equal but not hash-equal breaks every
    hash-based container the resolver puts it in.
    """
    x, y = TypeHint(hint), TypeHint(hint)
    assert x == y
    assert y == x
    assert hash(x) == hash(y)

    # `Any` hashes differently from every concrete hint, so it must not compare equal
    # to one either.
    if hash(TypeHint(hint)) != hash(TypeHint(Any)):
        assert TypeHint(hint) != TypeHint(Any)
        assert TypeHint(Any) != TypeHint(hint)


@pytest.mark.parametrize("hint", [int, Number, list, list[int], str, type(None)])
def test_beartype_orders_concrete_types_below_any(hint):
    """Plum relies on this ordering from `beartype`.

    Every concrete hint must be a subhint of `Any`. Plum normalises the *other*
    direction itself, in `_substitute_any`, because `beartype>=0.23` additionally
    makes `Any` a subhint of everything. If this assertion ever fails, `Any` has
    stopped being a supertype at all, and the resolver's notion of "least specific"
    goes with it.
    """
    assert TypeHint(hint) <= TypeHint(Any)


def test_dispatch_is_independent_of_beartype_any_ordering(dispatch: plum.Dispatcher):
    """Whichever way `beartype` orders `Any`, Plum's own ordering must not move.

    `beartype<0.23` and `beartype>=0.23` disagree on `TypeHint(Any) <= TypeHint(int)`,
    which is why Plum normalises `Any` rather than deferring to `beartype`. This test
    reads the raw ordering without asserting on it, and pins Plum's.
    """
    # Read, but deliberately do not assert on, `beartype`'s raw answer: it is `False`
    # before 0.23 and `True` from 0.23 onwards, and Plum must work either way.
    _ = TypeHint(Any) <= TypeHint(int)

    assert plum.Signature(int) < plum.Signature(Any)
    assert not plum.Signature(Any) < plum.Signature(int)
    assert plum.Signature(int) != plum.Signature(Any)
    assert plum.Signature(typing.Any) == plum.Signature(Any)

    @dispatch
    def f(x: int):
        return "int"

    @dispatch
    def f(x: Any):
        return "Any"

    assert f(1) == "int"
    assert f("x") == "Any"
