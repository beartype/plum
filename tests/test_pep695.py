"""Tests for PEP 695 type aliases (`type X = ...`).

The aliases here are built with `typing.TypeAliasType(...)` rather than the `type X
= ...` statement. The two produce the same object, but the statement is a syntax
error before Python 3.12, which would break collection of this module on 3.10/3.11.
"""

import sys
import typing
import warnings

import pytest

import plum
from plum import Dispatcher
from plum._type import is_faithful, resolve_type_hint

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="PEP 695 type aliases require Python 3.12 or later.",
)

T = typing.TypeVar("T")


def _alias(name, value, **kw):
    """Build a PEP 695 type alias, as `type {name} = {value}` would."""
    return typing.TypeAliasType(name, value, **kw)


def test_resolve_type_hint_preserves_alias() -> None:
    """`resolve_type_hint` returns an alias unchanged, without warning.

    The alias is deliberately not unwrapped: plum prints `Signature`s from the hints
    it stores, so unwrapping would replace the name the user wrote with its
    expansion.
    """
    X = _alias("X", int)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert resolve_type_hint(X) is X


def test_resolve_type_hint_preserves_subscripted_alias() -> None:
    """`resolve_type_hint` returns a subscripted alias unchanged."""
    Boxy = _alias("Boxy", list[T], type_params=(T,))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert resolve_type_hint(Boxy[int]) is not None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (int, True),  # A faithful target makes the alias faithful.
        (int | float, True),
        (list[int], False),  # An unfaithful target makes the alias unfaithful.
    ],
)
def test_is_faithful_unwraps_alias(value, expected) -> None:
    """Faithfulness is a property of the aliased hint, not of the alias."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert is_faithful(_alias("X", value)) is expected


def test_is_faithful_unwraps_subscripted_alias() -> None:
    """Faithfulness looks through a subscripted alias to the substituted hint."""
    Boxy = _alias("Boxy", list[T], type_params=(T,))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert is_faithful(Boxy[int]) is False


def test_dispatch_on_aliases() -> None:
    """Dispatch distinguishes two aliases of different types."""
    X = _alias("X", str)
    Y = _alias("Y", int)
    dispatch = Dispatcher()

    @dispatch
    def f(x: X):
        return "str"

    @dispatch
    def f(x: Y):
        return "int"

    assert f("1") == "str"
    assert f(1) == "int"


def test_dispatch_on_subscripted_aliases() -> None:
    """Dispatch distinguishes an alias subscripted by different child hints."""
    Boxy = _alias("Boxy", list[T], type_params=(T,))
    dispatch = Dispatcher()

    @dispatch
    def g(x: Boxy[int]):
        return "int"

    @dispatch
    def g(x: Boxy[str]):
        return "str"

    assert g([1]) == "int"
    assert g(["a"]) == "str"


def test_dispatch_alias_precedence() -> None:
    """An alias takes part in precedence exactly as the hint it aliases does."""
    X = _alias("X", str)
    dispatch = Dispatcher()

    @dispatch
    def h(x: object):
        return "object"

    @dispatch
    def h(x: X):
        return "str"

    assert h("s") == "str"
    assert h(object()) == "object"


def test_dispatch_alias_interchangeable_with_target() -> None:
    """An alias and the hint it aliases are the same type for dispatch."""
    Nums = _alias("Nums", int | float)
    dispatch = Dispatcher()

    @dispatch
    def k(x: Nums):
        return "num"

    @dispatch
    def k(x: str):
        return "str"

    assert k(1) == "num"
    assert k(1.0) == "num"
    assert k("s") == "str"


def test_signature_repr_keeps_alias_name() -> None:
    """A `Signature` prints the alias the user wrote, not its expansion."""
    X = _alias("X", str)
    Nums = _alias("Nums", int | float)
    dispatch = Dispatcher()

    @dispatch
    def m(x: X, y: Nums):
        return 1

    m("a", 1)

    signature = dispatch.functions["m"].methods[0].signature
    assert repr(signature) == "Signature(X, Nums)"
    assert plum.repr.repr_short(X) == "X"


def test_no_warnings_on_alias_annotations() -> None:
    """Annotating with an alias emits no warnings."""
    X = _alias("X", str)
    dispatch = Dispatcher()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @dispatch
        def n(x: X):
            return 1

        n("a")

    assert [str(w.message) for w in caught] == []
