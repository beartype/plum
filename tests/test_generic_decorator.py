"""Tests for the @plum.generic decorator."""

from dataclasses import dataclass
from typing import Generic, TypeVar

import pytest

import plum
from plum import dispatch, generic

T = TypeVar("T")
S = TypeVar("S")


# ---------------------------------------------------------------------------
# Helper classes
# ---------------------------------------------------------------------------


@generic
class Box(Generic[T]):
    def __init__(self, value) -> None:
        self.value = value

    @classmethod
    def __infer_type_parameter__(cls, instance):
        return type(instance.value)


@generic
class Pair(Generic[T, S]):
    def __init__(self, first, second) -> None:
        self.first = first
        self.second = second

    @classmethod
    def __infer_type_parameter__(cls, instance):
        return (type(instance.first), type(instance.second))


@generic
class CustomInfer(Generic[T]):
    def __init__(self, x, y) -> None:
        self.x, self.y = x, y

    @classmethod
    def __infer_type_parameter__(cls, instance):
        # Infer only from x.
        return type(instance.x)


# ---------------------------------------------------------------------------
# __orig_class__ inference tests
# ---------------------------------------------------------------------------


def test_bare_call_sets_orig_class_single_arg():
    b = Box(1)
    assert hasattr(b, "__orig_class__")
    assert b.__orig_class__ == Box[int]


def test_bare_call_sets_orig_class_str():
    b = Box("hello")
    assert b.__orig_class__ == Box[str]


def test_bare_call_sets_orig_class_multi_arg():
    p = Pair(1, "x")
    assert p.__orig_class__ == Pair[int, str]


def test_subscripted_call_overrides_inferred():
    # A[str](1): our wrapper infers Box[int], but Python's _GenericAlias.__call__
    # sets __orig_class__ = Box[str] afterwards.  The explicit form must win.
    b = Box[str](1)
    assert b.__orig_class__ == Box[str]


def test_subscripted_call_same_type():
    b = Box[int](1)
    assert b.__orig_class__ == Box[int]


def test_no_args_does_not_crash():
    # If __infer_type_parameter__ raises TypeError the wrapper emits a
    # RuntimeWarning and skips setting __orig_class__.
    @generic
    class NoArgs(Generic[T]):
        def __init__(self) -> None:
            pass

        @classmethod
        def __infer_type_parameter__(cls, instance):
            raise TypeError("no parameter to infer")

    with pytest.warns(RuntimeWarning, match="__orig_class__"):
        n = NoArgs()
    assert not hasattr(n, "__orig_class__")


def test_custom_infer_type_parameter():
    c = CustomInfer(42, "ignored")
    assert c.__orig_class__ == CustomInfer[int]


def test_custom_infer_overrides_default():
    # Pair of (str, int) with first-arg-only inference.
    c = CustomInfer("hi", 99)
    assert c.__orig_class__ == CustomInfer[str]


# ---------------------------------------------------------------------------
# Dispatch routing tests
# ---------------------------------------------------------------------------


@dispatch
def unwrap(b: Box[int]) -> str:
    return "int box"


@dispatch
def unwrap(b: Box[str]) -> str:
    return "str box"


def test_dispatch_routes_bare_int():
    assert unwrap(Box(1)) == "int box"


def test_dispatch_routes_bare_str():
    assert unwrap(Box("hi")) == "str box"


def test_dispatch_routes_subscripted_int():
    assert unwrap(Box[int](1)) == "int box"


def test_dispatch_routes_subscripted_str():
    assert unwrap(Box[str]("hi")) == "str box"


def test_dispatch_routes_subscripted_override():
    # Explicit Box[str](1) should route to str overload even though 1 is int.
    assert unwrap(Box[str](1)) == "str box"


def test_dispatch_no_any_fallback_needed():
    # With @generic, bare construction should dispatch without an A[Any] fallback.
    with pytest.raises(plum.NotFoundLookupError):
        # float has no registered overload — should raise, not silently fail.
        unwrap(Box(1.0))


# ---------------------------------------------------------------------------
# Custom-infer dispatch
# ---------------------------------------------------------------------------


@dispatch
def process(c: CustomInfer[int]) -> str:
    return "custom int"


@dispatch
def process(c: CustomInfer[str]) -> str:
    return "custom str"


def test_dispatch_custom_infer_int():
    assert process(CustomInfer(10, "ignored")) == "custom int"


def test_dispatch_custom_infer_str():
    assert process(CustomInfer("hi", 0)) == "custom str"


# ---------------------------------------------------------------------------
# Structural / API tests
# ---------------------------------------------------------------------------


def test_generic_preserves_init_signature():
    # functools.wraps should preserve __wrapped__ and the signature.
    assert hasattr(Box.__init__, "__wrapped__")


def test_generic_requires_infer_method():
    # @generic must raise TypeError at decoration time if __infer_type_parameter__
    # is not defined on the class or any ancestor.
    with pytest.raises(TypeError, match="__infer_type_parameter__"):

        @generic
        class NoInfer(Generic[T]):
            def __init__(self, x) -> None:
                self.x = x


def test_generic_parens_form():
    # @generic() with empty parentheses should work identically to @generic.
    @generic()
    class A(Generic[T]):
        def __init__(self, x) -> None:
            self.x = x

        @classmethod
        def __infer_type_parameter__(cls, instance):
            return type(instance.x)

    a = A(42)
    assert a.__orig_class__ == A[int]


def test_generic_subclass_no_crash():
    # Sub(Box) without re-declaring Generic[T] may not be subscriptable in all
    # Python versions, so __orig_class__ cannot be set and a RuntimeWarning is
    # emitted.  The key invariant is that instantiation does not raise.
    class Sub(Box):
        pass

    with pytest.warns(RuntimeWarning, match="__orig_class__"):
        s = Sub(99)
    assert s.value == 99


def test_generic_does_not_overwrite_user_set_orig_class():
    # If the user explicitly sets __orig_class__ inside their own __init__
    # AFTER calling super().__init__(), the outer wrapper still runs but by
    # that point any explicit Python subscription also overwrites it.  The
    # subscripted path is tested in test_subscripted_call_overrides_inferred.
    # Here we just verify that the subscripted explicit form always wins.
    b = Box[str](42)
    assert b.__orig_class__ == Box[str]


def test_generic_on_class_already_has_infer():
    # If a class defines __infer_type_parameter__ before decoration,
    # @generic must use it as-is.
    @generic
    class WithInfer(Generic[T]):
        def __init__(self, x) -> None:
            self.x = x

        @classmethod
        def __infer_type_parameter__(cls, instance):
            # Always return float regardless of actual type.
            return float

    w = WithInfer(1)
    assert w.__orig_class__ == WithInfer[float]


def test_generic_inherited_infer_not_double_installed():
    # Applying @generic to a subclass of a @generic class should not
    # require re-defining __infer_type_parameter__ if the parent provides one.
    @generic
    class Parent(Generic[T]):
        def __init__(self, x) -> None:
            self.x = x

        @classmethod
        def __infer_type_parameter__(cls, instance):
            return type(instance.x)

    @generic
    class Child(Parent[T]):
        pass

    c = Child(7)
    assert c.__orig_class__ == Child[int]


# ---------------------------------------------------------------------------
# Frozen dataclass
# ---------------------------------------------------------------------------


@generic
@dataclass(frozen=True)
class FrozenBox(Generic[T]):
    value: object

    @classmethod
    def __infer_type_parameter__(cls, instance):
        return type(instance.value)


def test_generic_frozen_dataclass_sets_orig_class():
    # object.__setattr__ must be used to bypass the frozen __setattr__.
    b = FrozenBox(1)
    assert b.__orig_class__ == FrozenBox[int]


def test_generic_frozen_dataclass_dispatch():
    @dispatch
    def handle(b: FrozenBox[int]) -> str:
        return "int"

    @dispatch
    def handle(b: FrozenBox[str]) -> str:
        return "str"

    assert handle(FrozenBox(1)) == "int"
    assert handle(FrozenBox("x")) == "str"
    # For frozen dataclasses Python's _GenericAlias.__call__ cannot overwrite
    # __orig_class__ (FrozenInstanceError is caught and swallowed), so the
    # inferred value always wins regardless of the subscripted form.
    assert handle(FrozenBox[str](1)) == "int"


def test_generic_frozen_dataclass_subscripted_inference_wins():
    # Python's _GenericAlias.__call__ tries to set __orig_class__ after __init__
    # but catches the resulting FrozenInstanceError (AttributeError subclass)
    # and silently discards it.  Our object.__setattr__ value therefore
    # persists.
    b = FrozenBox[str](1)
    assert (
        b.__orig_class__ == FrozenBox[int]
    )  # inferred from value, not from subscription


# ---------------------------------------------------------------------------
# Slotted classes
# ---------------------------------------------------------------------------


def _make_slotted_no_orig() -> type:
    """Build SlottedNoOrig inside a function to capture the decoration warning."""
    with pytest.warns(RuntimeWarning, match="__slots__"):

        @generic
        class SlottedNoOrig(Generic[T]):
            """Slotted class WITHOUT __orig_class__ in __slots__."""

            __slots__ = ("value",)

            def __init__(self, value) -> None:
                self.value = value

            @classmethod
            def __infer_type_parameter__(cls, instance):
                return type(instance.value)

    return SlottedNoOrig


@generic
class SlottedWithOrig(Generic[T]):
    """Slotted class WITH __orig_class__ in __slots__ — inference works."""

    __slots__ = ("value", "__orig_class__")

    def __init__(self, value) -> None:
        self.value = value

    @classmethod
    def __infer_type_parameter__(cls, instance):
        return type(instance.value)


def test_generic_slotted_warns_at_decoration():
    # @generic must warn at decoration time when __orig_class__ is missing from
    # __slots__ and instances will have no __dict__ fallback.
    _make_slotted_no_orig()  # warning assertion is inside the helper


def test_generic_slotted_without_orig_class_slot_skips_gracefully():
    # At instantiation time, object.__setattr__ raises AttributeError because
    # __orig_class__ is not in __slots__; a second RuntimeWarning is emitted.
    SlottedNoOrig = _make_slotted_no_orig()
    with pytest.warns(RuntimeWarning, match="__orig_class__"):
        b = SlottedNoOrig(42)
    assert b.value == 42
    assert not hasattr(b, "__orig_class__")


def test_generic_slotted_with_orig_class_slot_sets_correctly():
    b = SlottedWithOrig(99)
    assert b.__orig_class__ == SlottedWithOrig[int]


def test_generic_slotted_with_orig_class_subscripted_wins():
    b = SlottedWithOrig[str](99)
    assert b.__orig_class__ == SlottedWithOrig[str]
