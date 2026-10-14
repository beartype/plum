"""Dispatch on user-defined :class:`typing.Generic` subclasses."""

import re
import warnings
from collections.abc import Iterable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import (
    Annotated,
    Any,
    Generic,
    Literal,
    SupportsAbs,
    TypeVar,
    Union,
)

import pytest

from beartype.vale import Is

import plum
from plum import Dispatcher, NotFoundLookupError, generic
from plum._signature import Signature
from plum._type import (
    KeyPart,
    ResolvableType,
    _cache_spec,
    _is_generic_hint,
    is_cacheable,
    is_faithful,
    resolve_type_hint,
)

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
U = TypeVar("U")


class Box(Generic[T]):
    def __init__(self, v: Any) -> None:
        self.v = v


class CoBox(Generic[T_co]):
    def __init__(self, v: Any) -> None:
        self.v = v


class Pair(Generic[T, U]):
    def __init__(self, a: Any, b: Any) -> None:
        self.a = a
        self.b = b


class IntBox(Box[int]):
    def __init__(self) -> None:
        super().__init__(1)


class StrBox(Box[str]):
    def __init__(self) -> None:
        super().__init__("a")


def test_dispatch_on_user_generic():
    """Test that `Box[int]` and `Box[str]` are told apart, and cached separately."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[int]):
        return "int"

    @dispatch
    def f(x: Box[str]):
        return "str"

    assert f(Box[int](1)) == "int"
    assert f(Box[str]("a")) == "str"
    # A subclass of a parametrised generic records its parameter in `__orig_bases__`.
    assert f(IntBox()) == "int"
    assert f(StrBox()) == "str"
    with pytest.raises(NotFoundLookupError):
        f(Box(1.0))

    assert f._resolver.cache_spec == frozenset({KeyPart.GENERIC})
    assert set(f._cache) == {
        ((Box, Box[int]),),
        ((Box, Box[str]),),
        ((IntBox, None),),
        ((StrBox, None),),
    }
    assert not f._verify_cache


def test_bare_fallback():
    """Test that a bare `Box` method catches exactly the values without a parameter."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box):
        return "bare"

    @dispatch
    def f(x: Box[int]):
        return "int"

    assert f(Box[int](1)) == "int"
    assert f(Box(1)) == "bare"
    # A second bare value must reuse the bare entry, not the parametrised one.
    assert f(Box("a")) == "bare"
    assert f(IntBox()) == "int"
    assert set(f._cache) == {((Box, Box[int]),), ((Box, None),), ((IntBox, None),)}
    assert Signature(Box[int]) < Signature(Box)


@pytest.mark.parametrize(
    ("hint_a", "a", "hint_b", "b"),
    [
        (
            Pair[int, str],
            Pair[int, str](1, "a"),
            Pair[str, int],
            Pair[str, int]("a", 1),
        ),
        (Box[list[int]], Box[list[int]]([1]), Box[list[str]], Box[list[str]](["a"])),
        (Box[int] | Box[str], Box[str]("a"), Box[float], Box[float](1.0)),
    ],
)
def test_dispatch_on_composite_generic(hint_a, a, hint_b, b):
    """Test dispatch on a multi-parameter, nested, or union of user generics."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: hint_a):
        return "a"

    @dispatch
    def f(x: hint_b):
        return "b"

    assert f(a) == "a"
    assert f(b) == "b"


def test_variance():
    """Test that `CoBox[bool]` matches `CoBox[int]`."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: CoBox[int]):
        return "int"

    assert f(CoBox[bool](True)) == "int"


def test_generic_is_cacheable_via_the_generic_key_part() -> None:
    """A parametrised user generic is cacheable through `KeyPart.GENERIC`."""
    assert _cache_spec(resolve_type_hint(Box[int])) == frozenset({KeyPart.GENERIC})
    assert is_cacheable(Box[int])
    # Cacheable, but not faithful: the key needs more than `type(x)`.
    assert not is_faithful(Box[int])
    # The bare class stays faithful.
    assert is_faithful(Box)
    # A faithful type in a union adds no key part.
    assert _cache_spec(resolve_type_hint(Box[int] | None)) == frozenset(
        {KeyPart.GENERIC}
    )


def test_hints_that_inspect_elements_stay_uncacheable() -> None:
    """Only hints matched through `__orig_class__` may become cacheable.

    `is_bearable([1], list[int])` and `is_bearable(["a"], list[int])` disagree for
    two values of the same runtime type, so no key built from the type can decide
    it. Anything that contains such a hint must stay uncacheable too.
    """
    for hint in (
        list[int],
        dict[str, int],
        tuple[int, ...],
        list[Box[int]],
        Box[int] | list[int],
        Annotated[Box[int], Is[lambda x: True]],
    ):
        assert is_cacheable(hint) is False, hint


def test_values_without_orig_class_share_a_verdict() -> None:
    """Values of one runtime type and no `__orig_class__` must match alike.

    This is what makes `KeyPart.GENERIC` sound: such values are decided by their
    runtime class alone, which the key already carries.
    """
    bare = [Box(1), Box("a"), Box([1]), Box(None), Box(Box(1))]
    int_boxes, str_boxes = [IntBox(), IntBox()], [StrBox(), StrBox()]
    int_boxes[1].v = "a"
    str_boxes[1].v = 1
    for hint in (Box[int], Box[str], Box[list[int]], Box):
        signature = Signature(hint)
        for group in (bare, int_boxes, str_boxes):
            assert len({signature.match((v,)) for v in group}) == 1, (hint, group)


def test_parametrised_builtins_still_use_the_verify_cache() -> None:
    """Test that a `list[int]` method is not cacheable."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: list[int]) -> str:
        return "int"

    @dispatch
    def f(x: list[str]) -> str:
        return "str"

    assert f([1]) == "int"
    assert f._resolver.cache_spec is None
    assert not f._cache
    assert f._verify_cache
    assert f(["a"]) == "str"


def test_might_match_includes_generic_methods() -> None:
    """`might_match` must never exclude a `Box[int]` method for a runtime `Box`."""
    for value in (Box[int](1), Box[str]("a"), Box(1), IntBox(), StrBox()):
        assert Signature(Box[int]).might_match((value,))
        assert Signature(Box).might_match((value,))
    assert not Signature(Box[int]).might_match((1,))


def test_resolve_type_hint_resolves_generic_arguments():
    """Test that `resolve_type_hint` resolves a `ResolvableType` in a user generic."""
    t = ResolvableType("t")
    t.deliver(int)
    assert resolve_type_hint(Box[t]) == Box[int]
    assert resolve_type_hint(Pair[t, str]) == Pair[int, str]


def test_no_warning_for_generic_hints(recwarn: pytest.WarningsRecorder) -> None:
    """Registering a generic method must not warn about unresolvable hints."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[int]) -> str:
        return "int"

    assert f(Box[int](1)) == "int"
    assert [w for w in recwarn.list if "Could not" in str(w.message)] == []


def test_generic_defined_in_an_exec_namespace():
    """Test that a generic whose module is `builtins`, as in a doctest, dispatches."""
    ns = {}
    exec(
        "from typing import Generic, TypeVar\n"
        'T = TypeVar("T")\n'
        "class Box(Generic[T]):\n"
        "    def __init__(self, v): self.v = v\n",
        ns,
    )
    box = ns["Box"]
    assert box.__module__ == "builtins"
    assert is_cacheable(box[int])

    dispatch = Dispatcher()

    @dispatch
    def f(x: box[int]):
        return "int"

    @dispatch
    def f(x: box[str]):
        return "str"

    assert f(box[int](1)) == "int"
    assert f(box[str]("a")) == "str"


def test_gate_excludes_builtins_abcs_and_special_forms() -> None:
    """Only true `Generic` subclasses take the `__orig_class__` path."""
    for hint in (
        list[int],
        dict[str, int],
        tuple[int, ...],
        set[int],
        Sequence[int],
        Iterable[int],
        Mapping[str, int],
        re.Pattern[str],
        AbstractContextManager[int],
        type[int],
        Literal[1],
        Annotated[int, "meta"],
        Union[int, str],  # noqa: UP007
        int,
        Box,
    ):
        assert not _is_generic_hint(hint), hint

    for hint in (Box[int], Pair[int, str], CoBox[int], Box[list[int]]):
        assert _is_generic_hint(hint), hint


def test_generic_varargs():
    """Test dispatch on varargs of a user generic."""
    dispatch = Dispatcher()

    @dispatch
    def f(*xs: Box[int]) -> str:
        return "ints"

    @dispatch
    def f(*xs: Box[str]) -> str:
        return "strs"

    assert f(Box[int](1), Box[int](2)) == "ints"
    assert f(Box[str]("a")) == "strs"


def test_unhashable_parametrisation():
    """Test that an unhashable parametrisation dispatches, and its cache is capped."""
    from plum._function import _VALUE_CACHE_LIMIT

    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[int]):
        return "box"

    @dispatch
    def f(x: object):
        return "object"

    with pytest.raises(TypeError):
        hash(Box[Annotated[int, {}]])
    x = Box[Annotated[int, {}]](1)
    assert f(x) == "box"
    assert f(x) == "box"
    # `typing` does not cache an unhashable parametrisation, so each one is a new key.
    for i in range(_VALUE_CACHE_LIMIT):
        assert f(Box[Annotated[int, {"a": i}]](i)) == "box"
    assert len(f._cache) == _VALUE_CACHE_LIMIT
    assert f(Box[str]("a")) == "object"


def test_parametrised_protocol_is_matched_by_structure():
    """Test that a parametrised protocol is not matched by `__orig_class__`."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: SupportsAbs[int]):
        return "abs"

    @dispatch
    def f(x: object):
        return "object"

    assert f(-1) == "abs"


@generic
class InferredBox(Generic[T]):
    def __init__(self, value: Any) -> None:
        self.value = value

    @classmethod
    def __infer_type_parameter__(cls, instance: "InferredBox[Any]") -> type:
        return type(instance.value)


@generic
class InferredPair(Generic[T, U]):
    def __init__(self, a: Any, b: Any) -> None:
        self.a = a
        self.b = b

    @classmethod
    def __infer_type_parameter__(
        cls, instance: "InferredPair[Any, Any]"
    ) -> tuple[type, type]:
        return type(instance.a), type(instance.b)


class InferredSubBox(InferredBox[T]):
    """A generic subclass: it must infer *its own* parametrisation."""


def test_bare_instantiation_dispatches() -> None:
    """Test that a bare instantiation dispatches like a subscripted one."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: InferredBox[int]) -> str:
        return "InferredBox[int]"

    @dispatch
    def f(x: InferredBox[str]) -> str:
        return "InferredBox[str]"

    @dispatch
    def f(x: InferredPair[int, str]) -> str:
        return "InferredPair[int, str]"

    @dispatch
    def f(x: InferredPair[str, int]) -> str:
        return "InferredPair[str, int]"

    assert f(InferredBox(1)) == "InferredBox[int]"
    assert f(InferredBox("a")) == "InferredBox[str]"
    assert f(InferredPair(1, "a")) == "InferredPair[int, str]"
    assert f(InferredPair("a", 1)) == "InferredPair[str, int]"


def test_explicit_subscript_overrides_inference() -> None:
    """Test that an explicit subscript wins over the inferred parameter."""
    assert InferredBox[str](1).__orig_class__ == InferredBox[str]


def test_unusable_class_raises_at_decoration() -> None:
    """Test that `@generic` rejects a class that it cannot parametrise."""

    class NoHook(Generic[T]):
        pass

    class NonCallableHook(Generic[T]):
        __infer_type_parameter__ = 42

    class NotGeneric:
        @classmethod
        def __infer_type_parameter__(cls, instance: Any) -> type:
            return int

    with pytest.raises(TypeError, match=r"NoHook.*__infer_type_parameter__"):
        generic(NoHook)
    with pytest.raises(TypeError, match=r"NonCallableHook.*__infer_type_parameter__"):
        generic(NonCallableHook)
    with pytest.raises(TypeError, match=r"NotGeneric.*typing\.Generic"):
        generic(NotGeneric)


def test_slots_without_orig_class_warn() -> None:
    """Test that a class that cannot carry `__orig_class__` warns, but constructs."""
    with pytest.warns(RuntimeWarning, match=r"__slots__.*__orig_class__"):

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


def test_concrete_subclass_does_not_warn() -> None:
    """Test that a subclass with no parameters left constructs without a warning."""

    class IntBox(InferredBox[int]):
        pass

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        instance = IntBox(1)
    assert not hasattr(instance, "__orig_class__")


def test_frozen_dataclass() -> None:
    """Test that `__orig_class__` is set on a frozen dataclass."""

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
    """Test that a generic subclass infers its own parametrisation."""
    assert InferredSubBox(1).__orig_class__ == InferredSubBox[int]

    dispatch = Dispatcher()

    @dispatch
    def f(b: InferredBox[int]) -> str:
        return "InferredBox"

    @dispatch
    def f(b: InferredSubBox[int]) -> str:
        return "InferredSubBox"

    assert f(InferredSubBox(1)) == "InferredSubBox"
    assert f(InferredBox(1)) == "InferredBox"


def test_init_metadata_is_preserved() -> None:
    """Test that the wrapped `__init__` keeps its name and docstring."""

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


def test_generic_is_exported() -> None:
    assert plum.generic is generic
    assert "generic" in plum.__all__


@pytest.mark.parametrize(
    ("slots", "inherit"),
    [
        pytest.param(("__orig_class__",), False, id="own-slot"),
        pytest.param("__orig_class__", False, id="string-slots"),
        pytest.param(("__dict__",), False, id="dict-slot"),
        pytest.param((), True, id="inherited-slot"),
    ],
)
def test_slots_that_can_carry_orig_class(slots: Any, inherit: bool) -> None:
    """Test that a slotted class that can carry `__orig_class__` does not warn."""

    class Base:
        __slots__ = ("__orig_class__",)

    bases = (Base, Generic[T]) if inherit else (Generic[T],)

    with warnings.catch_warnings():
        warnings.simplefilter("error")

        @generic
        class C(*bases):
            __slots__ = slots

            @classmethod
            def __infer_type_parameter__(cls, instance: Any) -> type:
                return int

        assert C().__orig_class__ == C[int]


def test_init_returning_a_value_raises() -> None:
    """Test that `@generic` does not hide an `__init__` that returns a value."""

    @generic
    class C(Generic[T]):
        def __init__(self):
            return 1  # noqa: PLE0101

        @classmethod
        def __infer_type_parameter__(cls, instance: Any) -> type:
            return int

    # The message differs when `_generic` is compiled.
    with pytest.raises(TypeError):
        C()
