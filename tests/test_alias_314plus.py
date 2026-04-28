import functools as ft
import sys
from typing import Union, get_args
from typing_extensions import TypeAliasType

import pytest

import beartype
import beartype.door

import plum

# These tests are for Python 3.14 and later only.
pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Union aliasing tests for Python 3.14 and later only.",
)


def test_activate_union_aliases() -> None:
    """Test that a`ctivate_union_aliases` sets `_ALIASES_ARE_ACTIVE` to `True`."""
    plum._alias._ALIASES_ARE_ACTIVE = False
    plum.activate_union_aliases()
    assert plum._alias._ALIASES_ARE_ACTIVE is True


def test_deactivate_union_aliases() -> None:
    """Test that `deactivate_union_aliases` sets `_ALIASES_ARE_ACTIVE` to `False`."""
    plum._alias._ALIASES_ARE_ACTIVE = True
    plum.deactivate_union_aliases()
    assert plum._alias._ALIASES_ARE_ACTIVE is False


@pytest.mark.parametrize("union", [int | str, Union[int, str]])  # noqa: UP007
def test_repr_short_uses_alias(union) -> None:
    """Test that `repr_short` substitutes registered union aliases."""
    plum.set_union_alias(union, alias="IntStr")

    # Aliased union should use the alias name.
    assert plum.repr.repr_short(int | str) == "IntStr"
    assert plum.repr.repr_short(Union[int, str]) == "IntStr"  # noqa: UP007

    # Non-aliased unions should be unchanged.
    assert "IntStr" not in plum.repr.repr_short(int | float)
    assert "IntStr" not in plum.repr.repr_short(Union[int, float])  # noqa: UP007

    # Plain types should be unchanged.
    assert plum.repr.repr_short(int) == "int"
    assert plum.repr.repr_short(float) == "float"

    # Signature printing should use the alias.
    sig = plum.Signature(int | str, float)
    assert "IntStr" in repr(sig)
    assert repr(sig) == "Signature(IntStr, float)"

    # Signature printing should use the alias.
    sig = plum.Signature(Union[int, str], float)  # noqa: UP007
    assert "IntStr" in repr(sig)
    assert repr(sig) == "Signature(IntStr, float)"


@pytest.mark.parametrize("display", [plum.repr.repr_short])
def test_union_alias(display):
    plum.set_union_alias(int | str, alias="IntStr")

    # Check that the alias is used after registration.
    assert display(Union[int, str]) == "IntStr"  # noqa: UP007

    # Register a simple alias and check that it prints correctly.
    IntStr = plum.set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007
    assert display(IntStr) == "IntStr"  # noqa: UP007
    assert display(Union[int, str]) == "IntStr"  # noqa: UP007

    # Register a bigger alias.
    plum.set_union_alias(Union[int, str, float], alias="IntStrFloat")  # noqa: UP007
    assert display(Union[int, str, float]) == "IntStrFloat"  # noqa: UP007


@pytest.mark.parametrize("display", [plum.repr.repr_short])
def test_uniontype_alias(display):
    plum.set_union_alias(int | str, alias="IntStr")

    # Check that the alias is used after registration.
    assert display(int | str) == "IntStr"

    # Register a simple alias and check that it prints correctly.
    IntStr = plum.set_union_alias(int | str, alias="IntStr")  # noqa: UP007
    assert display(IntStr) == "IntStr"  # noqa: UP007
    assert display(int | str) == "IntStr"  # noqa: UP007

    # Register a bigger alias.
    plum.set_union_alias(int | str | float, alias="IntStrFloat")  # noqa: UP007
    assert display(int | str | float) == "IntStrFloat"  # noqa: UP007


def test_repr_short_with_type_alias_type_passthrough():
    """Test that `repr_short` handles a `TypeAliasType` passed directly.

    This exercises the early-return path in `_transform_union_alias` where the
    input is already a `TypeAliasType` instance.
    """

    alias = TypeAliasType("MyAlias", int | str)
    assert plum.repr.repr_short(alias) == "MyAlias"


def test_optional():
    assert repr(Union[int, None]) == "int | None"  # noqa: UP007
    assert repr(Union[None, int]) == "None | int"  # noqa: UP007
    assert repr(int | None) == "int | None"


def test_double_registration_union_same_alias() -> None:
    """Test that registering the same union with the same alias is OK."""
    plum.set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007
    plum.set_union_alias(Union[int, str], alias="IntStr")  # This is OK  # noqa: UP007


def test_double_registration_uniontype_same_alias() -> None:
    """Test that registering the same union with the same alias is OK."""
    plum.set_union_alias(int | str, alias="IntStr")
    plum.set_union_alias(int | str, alias="IntStr")  # This is OK


def test_double_registration_different_alias() -> None:
    """Test that registering the same union with a different alias raises an error."""
    plum.set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007
    with pytest.raises(RuntimeError, match=r"already has alias"):
        plum.set_union_alias(Union[int, str], alias="OtherIntStr")  # noqa: UP007


def test_double_registration():
    # We can register with the same alias, but not with a different alias.
    plum.set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007
    with pytest.raises(RuntimeError, match=r"already has alias"):
        plum.set_union_alias(Union[int, str], alias="OtherIntStr")  # noqa: UP007
    with pytest.raises(RuntimeError, match=r"already has alias"):
        plum.set_union_alias(int | str, alias="OtherIntStr")

    # The same applies for Union types.
    plum.set_union_alias(str | None, alias="OptStr")
    with pytest.raises(RuntimeError, match=r"already has alias"):
        plum.set_union_alias(str | None, alias="OtherOptStr")  # noqa: UP007
    with pytest.raises(RuntimeError, match=r"already has alias"):
        plum.set_union_alias(Union[str | None], alias="OtherIntStr")  # noqa: UP007

    # We can also register plain types, but the same rules apply.
    plum.set_union_alias(int, alias="MyInt")
    plum.set_union_alias(int, alias="MyInt")  # This is OK.
    with pytest.raises(RuntimeError, match=r"already has alias"):
        plum.set_union_alias(int, alias="MyOtherInt")


def test_set_union_alias_generated_type_alias() -> None:
    """Test that `set_union_alias` generates a `TypeAliasType` for unions."""
    plum.set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007

    IntStr = plum._alias._ALIASED_UNIONS[(int, str)]

    # The returned value should be a `TypeAliasType`.
    assert hasattr(IntStr, "__name__")
    assert IntStr.__name__ == "IntStr"
    assert hasattr(IntStr, "__value__")
    # The underlying value should be the union.

    assert set(get_args(IntStr.__value__)) == {int, str}


def test_dispatch_with_union_alias(dispatch: plum.Dispatcher) -> None:
    """Test that dispatch works correctly with union aliases."""
    # Register an alias for Union[int, str]
    plum.set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007

    # Define a function using the alias
    @dispatch
    def process(x: int | str) -> str:
        return "int or str"

    @dispatch
    def process(x: float) -> str:
        return "float"

    # Test dispatch
    assert process(42) == "int or str"
    assert process("hello") == "int or str"
    assert process(3.14) == "float"


def test_dispatch_with_union_directly(dispatch: plum.Dispatcher) -> None:
    """Test that dispatch works when using `Union` directly if registered."""
    # Register the alias
    plum.set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007

    # Define a function using Union directly (should still work)
    @dispatch
    def process(x: int | str) -> str:
        return "int or str"

    @dispatch
    def process(x: float) -> str:
        return "float"

    # Test dispatch
    assert process(42) == "int or str"
    assert process("hello") == "int or str"
    assert process(3.14) == "float"


def test_signature_printing_with_alias(dispatch: plum.Dispatcher) -> None:
    """Test that function signatures are nicely printed with `TypeAliasType` names."""
    # Register an alias.
    plum.set_union_alias(int | str, alias="IntStr")

    @dispatch
    def example(x: int | str, y: float) -> str:
        return "test"

    # Check that the signature contains the alias name. The signature should show
    # `IntStr` rather than `Union[int, str]`.
    sig_str = str(example.methods[0].signature)
    assert "IntStr" in sig_str


def test_beartype_strict_mode_compatibility(dispatch: plum.Dispatcher) -> None:
    """Test that strict `beartype` works with Plum dispatch on aliased unions."""
    original_is_bearable = plum._is_bearable

    # Temporarily set strict mode for this test.
    plum._is_bearable = ft.partial(
        beartype.door.is_bearable,
        conf=beartype.BeartypeConf(strategy=beartype.BeartypeStrategy.On),
    )

    try:
        # Register an alias.
        plum.set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007

        # Define a function using the alias with Plum dispatch.

        @dispatch
        def strict_process(x: int | str) -> str:
            return f"processed: {x}"

        # These should work.
        assert strict_process(42) == "processed: 42"
        assert strict_process("hello") == "processed: hello"

        # This should not match the signature (`float` is not in `IntStr`).
        with pytest.raises(plum.NotFoundLookupError):
            strict_process(3.14)
    finally:
        # Restore original.
        plum._is_bearable = original_is_bearable


def test_multiple_aliases_in_signature(dispatch: plum.Dispatcher) -> None:
    """Test that multiple aliased unions in the same signature work correctly."""
    # Register multiple aliases.
    plum.set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007
    plum.set_union_alias(Union[float, bool], alias="FloatBool")  # noqa: UP007

    @dispatch
    def multi(x: int | str, y: float | bool) -> str:
        return f"{x}, {y}"

    # Test various combinations.
    assert multi(42, 3.14) == "42, 3.14"
    assert multi("hello", True) == "hello, True"
    assert multi(100, False) == "100, False"
    assert multi("test", 2.5) == "test, 2.5"


def test_alias_in_method_repr(dispatch: plum.Dispatcher) -> None:
    """Test that aliased union names appear in `method.methods` repr."""
    plum.set_union_alias(int | str, alias="IntOrStr")

    @dispatch
    def method(x: int | str) -> str:
        return f"Integer: {x}"

    assert "IntOrStr" in repr(method.methods)


def test_alias_priority_in_dispatch(dispatch: plum.Dispatcher) -> None:
    """Test that aliased unions are treated like a union in dispatch."""
    # Register an alias.
    plum.set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007

    @dispatch
    def handle(x: int | str) -> str:
        return "alias"

    @dispatch
    def handle(x: int) -> str:
        return "int"

    # The more specific `int` should match first.
    assert handle(42) == "int"
    assert handle("hello") == "alias"
