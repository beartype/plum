"""The `@plum.generic` decorator: infer `__orig_class__` at construction."""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import pytest

import plum
from plum import Dispatcher, generic
from plum._type import KeyPart

T = TypeVar("T")
U = TypeVar("U")


# These live at module scope on purpose: the tier-one test needs a class whose
# module is a real one, and `Signature` caches on the class object.
@generic
class Box(Generic[T]):
    def __init__(self, value: Any) -> None:
        self.value = value

    @classmethod
    def __infer_type_parameter__(cls, instance: "Box[Any]") -> type:
        return type(instance.value)


@generic
class Pair(Generic[T, U]):
    def __init__(self, a: Any, b: Any) -> None:
        self.a = a
        self.b = b

    @classmethod
    def __infer_type_parameter__(cls, instance: "Pair[Any, Any]") -> tuple[type, type]:
        return type(instance.a), type(instance.b)


class SubBox(Box[T]):
    """A generic subclass: it must infer *its own* parametrisation."""


def test_bare_instantiation_infers_the_parameter() -> None:
    assert Box(1).__orig_class__ == Box[int]
    assert Box("a").__orig_class__ == Box[str]


def test_bare_instantiation_dispatches() -> None:
    dispatch = Dispatcher()

    @dispatch
    def unwrap(b: Box[int]) -> str:
        return "int"

    @dispatch
    def unwrap(b: Box[str]) -> str:
        return "str"

    assert unwrap(Box(1)) == "int"
    assert unwrap(Box("a")) == "str"


def test_explicit_subscript_overrides_inference() -> None:
    """Python sets `__orig_class__` after `__init__`, so the subscript wins."""
    b = Box[str](1)
    assert b.__orig_class__ == Box[str]

    dispatch = Dispatcher()

    @dispatch
    def unwrap(b: Box[int]) -> str:
        return "int"

    @dispatch
    def unwrap(b: Box[str]) -> str:
        return "str"

    # The value is an `int`, but the caller asked for `Box[str]`.
    assert unwrap(Box[str](1)) == "str"


def test_multi_parameter_generic() -> None:
    assert Pair(1, "a").__orig_class__ == Pair[int, str]

    dispatch = Dispatcher()

    @dispatch
    def f(p: Pair[int, str]) -> str:
        return "int,str"

    @dispatch
    def f(p: Pair[str, int]) -> str:
        return "str,int"

    assert f(Pair(1, "a")) == "int,str"
    assert f(Pair("a", 1)) == "str,int"


def test_missing_infer_type_parameter_raises_at_decoration() -> None:
    with pytest.raises(TypeError, match=r"NoInfer.*__infer_type_parameter__"):

        @generic
        class NoInfer(Generic[T]):
            def __init__(self, value: Any) -> None:
                self.value = value


def test_slots_without_orig_class_warns_at_decoration() -> None:
    with pytest.warns(RuntimeWarning, match=r"__slots__.*__orig_class__"):

        @generic
        class Slotted(Generic[T]):
            __slots__ = ("value",)

            def __init__(self, value: Any) -> None:
                self.value = value

            @classmethod
            def __infer_type_parameter__(cls, instance: Any) -> type:
                return type(instance.value)


def test_slots_including_orig_class_does_not_warn(
    recwarn: pytest.WarningsRecorder,
) -> None:
    @generic
    class Slotted(Generic[T]):
        __slots__ = ("__orig_class__", "value")

        def __init__(self, value: Any) -> None:
            self.value = value

        @classmethod
        def __infer_type_parameter__(cls, instance: Any) -> type:
            return type(instance.value)

    assert Slotted(1).__orig_class__ == Slotted[int]
    assert [w for w in recwarn.list if issubclass(w.category, RuntimeWarning)] == []


def test_construction_failure_warns_but_does_not_crash() -> None:
    """A slotted class still constructs; the write just warns."""
    with pytest.warns(RuntimeWarning, match="__slots__"):

        @generic
        class Slotted(Generic[T]):
            __slots__ = ("value",)

            def __init__(self, value: Any) -> None:
                self.value = value

            @classmethod
            def __infer_type_parameter__(cls, instance: Any) -> type:
                return type(instance.value)

    with pytest.warns(RuntimeWarning, match="could not set"):
        instance = Slotted(1)
    assert instance.value == 1
    assert not hasattr(instance, "__orig_class__")


def test_non_generic_subclass_warns_rather_than_crashing() -> None:
    """`SubBox[int]` is fine; a non-generic subclass cannot be subscripted."""

    class Concrete(Box[int]):
        def __init__(self) -> None:
            super().__init__(1)

    with pytest.warns(RuntimeWarning, match="could not set"):
        instance = Concrete()
    assert instance.value == 1


def test_frozen_dataclass() -> None:
    @generic
    @dataclass(frozen=True)
    class Frozen(Generic[T]):
        value: Any

        @classmethod
        def __infer_type_parameter__(cls, instance: Any) -> type:
            return type(instance.value)

    instance = Frozen(1)
    assert instance.value == 1
    assert instance.__orig_class__ == Frozen[int]


def test_inheritance_infers_the_subclass() -> None:
    """The wrapper parametrises `type(self)`, not the decorated class."""
    assert SubBox(1).__orig_class__ == SubBox[int]

    dispatch = Dispatcher()

    @dispatch
    def f(b: Box[int]) -> str:
        return "Box"

    @dispatch
    def f(b: SubBox[int]) -> str:
        return "SubBox"

    assert f(SubBox(1)) == "SubBox"
    assert f(Box(1)) == "Box"


def test_init_metadata_is_preserved() -> None:
    @generic
    class Documented(Generic[T]):
        def __init__(self, value: Any) -> None:
            """Wrap a value."""
            self.value = value

        @classmethod
        def __infer_type_parameter__(cls, instance: Any) -> type:
            return type(instance.value)

    assert Documented.__init__.__doc__ == "Wrap a value."
    assert Documented.__init__.__name__ == "__init__"
    assert Documented.__init__.__qualname__.endswith("Documented.__init__")


def test_decorated_dispatch_is_served_by_tier_one() -> None:
    """Bare construction routes through the `GENERIC` key part, and caches."""
    dispatch = Dispatcher()

    @dispatch
    def f(b: Box[int]) -> str:
        return "int"

    @dispatch
    def f(b: Box[str]) -> str:
        return "str"

    assert f(Box(1)) == "int"
    assert f._resolver.cache_spec == frozenset({KeyPart.GENERIC})
    assert set(f._cache) == {((Box, Box[int]),)}
    # Tier two is not involved at all.
    assert not f._verify_cache

    # A second call must be answered from the cache. Empty the resolver behind its
    # back — mutating the list leaves the cache intact — so any call that does reach
    # resolution fails loudly instead of quietly agreeing.
    f._resolver.methods.clear()
    assert f(Box(2)) == "int"
    assert set(f._cache) == {((Box, Box[int]),)}


def test_generic_is_exported() -> None:
    assert plum.generic is generic
    assert "generic" in plum.__all__


def test_generic_rejects_a_non_callable_infer_hook() -> None:
    """A non-callable `__infer_type_parameter__` must fail at decoration.

    Checking only that the attribute exists lets such a class decorate cleanly and
    then warn on every construction instead of failing once, loudly, up front.
    """

    class NotCallable(Generic[T]):
        __infer_type_parameter__ = 42

        def __init__(self, value: object) -> None:
            self.value = value

    with pytest.raises(TypeError, match="__infer_type_parameter__"):
        generic(NotCallable)
