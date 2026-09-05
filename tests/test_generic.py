"""Dispatch on user-defined :class:`typing.Generic` subclasses."""

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import AbstractContextManager
from typing import Annotated, Any, Generic, Literal, Optional, TypeVar, Union

import pytest

from beartype.door import TypeHint
from beartype.vale import Is

from plum import Dispatcher, NotFoundLookupError
from plum._signature import Signature
from plum._type import (
    KeyPart,
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


def test_dispatch_on_user_generic() -> None:
    """`Box[int]` and `Box[str]` are distinguished via `__orig_class__`."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[int]) -> str:
        return "int"

    @dispatch
    def f(x: Box[str]) -> str:
        return "str"

    assert f(Box[int](1)) == "int"
    assert f(Box[str]("a")) == "str"


def test_bare_fallback_coexists() -> None:
    """A bare `Box` method catches instances with no `__orig_class__`."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box) -> str:
        return "bare"

    @dispatch
    def f(x: Box[int]) -> str:
        return "int"

    assert f(Box[int](1)) == "int"
    assert f(Box(1)) == "bare"
    # A parametrised signature is strictly more specific than the bare one.
    assert Signature(Box[int]) <= Signature(Box)
    assert not Signature(Box) <= Signature(Box[int])


def test_no_matching_parameter_is_not_found() -> None:
    """Without a bare fallback, an unmatched parameter is a lookup error."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[int]) -> str:
        return "int"

    with pytest.raises(NotFoundLookupError):
        f(Box[str]("a"))
    with pytest.raises(NotFoundLookupError):
        f(Box(1.0))


def test_subclass_of_parametrised_generic() -> None:
    """`class IntBox(Box[int])` satisfies `Box[int]` via `__orig_bases__`."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[int]) -> str:
        return "int"

    @dispatch
    def f(x: Box[str]) -> str:
        return "str"

    assert f(IntBox()) == "int"
    assert f(StrBox()) == "str"


def test_multi_parameter_generic() -> None:
    dispatch = Dispatcher()

    @dispatch
    def f(x: Pair[int, str]) -> str:
        return "int,str"

    @dispatch
    def f(x: Pair[str, int]) -> str:
        return "str,int"

    assert f(Pair[int, str](1, "a")) == "int,str"
    assert f(Pair[str, int]("a", 1)) == "str,int"


def test_nested_generic() -> None:
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[list[int]]) -> str:
        return "list[int]"

    @dispatch
    def f(x: Box[list[str]]) -> str:
        return "list[str]"

    assert f(Box[list[int]]([1])) == "list[int]"
    assert f(Box[list[str]](["a"])) == "list[str]"


def test_variance_is_beartypes_call() -> None:
    """Plum holds no opinion on variance: assert what beartype actually does."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: CoBox[int]) -> str:
        return "int"

    # Beartype's subtype ordering is the single source of truth.
    covariant_ok = bool(TypeHint(CoBox[bool]) <= TypeHint(CoBox[int]))
    assert covariant_ok, "beartype changed its variance rule; update this test"
    assert f(CoBox[bool](True)) == "int"

    # Beartype applies the same rule to an *invariant* `TypeVar`.
    assert bool(TypeHint(Box[bool]) <= TypeHint(Box[int]))


def test_generic_is_cacheable_via_the_generic_key_part() -> None:
    """A parametrised user generic is cacheable through `KeyPart.GENERIC`."""
    assert _cache_spec(resolve_type_hint(Box[int])) == frozenset({KeyPart.GENERIC})
    assert is_cacheable(Box[int])
    # Cacheable, but not faithful: the key needs more than `type(x)`.
    assert not is_faithful(Box[int])
    # The bare class stays faithful.
    assert is_faithful(Box)
    # A union of generics composes; so does a generic beside a faithful type.
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


def test_generic_dispatch_is_served_by_tier_one() -> None:
    """Generic dispatch memoises the method: no resolver run on a warm call."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[int]) -> str:
        return "int"

    @dispatch
    def f(x: Box[str]) -> str:
        return "str"

    assert f(Box[int](1)) == "int"
    # `@dispatch` returns the `Function` itself.
    assert f._resolver.cache_spec == frozenset({KeyPart.GENERIC})
    # The key is the runtime type plus the recorded parametrisation.
    assert set(f._cache) == {((Box, Box[int]),)}
    # Tier two is not involved at all.
    assert not f._verify_cache
    # Warm dispatch still selects correctly, and each parametrisation gets its own
    # entry.
    assert f(Box[str]("a")) == "str"
    assert f(Box[int](2)) == "int"
    assert set(f._cache) == {((Box, Box[int]),), ((Box, Box[str]),)}


def test_bare_and_parametrised_values_do_not_collide() -> None:
    """Values with and without `__orig_class__` must not share a cache entry."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box) -> str:
        return "bare"

    @dispatch
    def f(x: Box[int]) -> str:
        return "int"

    assert f(Box[int](1)) == "int"
    assert f(Box(1)) == "bare"
    # A second bare value of the same type must reuse that entry, not the other.
    assert f(Box("a")) == "bare"
    assert f(IntBox()) == "int"
    assert f(Box[int](2)) == "int"
    assert set(f._cache) == {((Box, Box[int]),), ((Box, None),), ((IntBox, None),)}


def test_parametrised_builtins_still_use_the_verify_cache() -> None:
    """A `list[int]` method must keep routing to tier two."""
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


def test_resolve_type_hint_recurses_into_generics() -> None:
    """`resolve_type_hint` rebuilds user generics without warning."""
    assert resolve_type_hint(Box[int]) == Box[int]
    assert resolve_type_hint(Box[list[int]]) == Box[list[int]]
    assert resolve_type_hint(Pair[int, str]) == Pair[int, str]
    assert resolve_type_hint(Box) is Box


def test_resolve_type_hint_leaves_special_forms_alone() -> None:
    """Special forms must be untouched by the new generic branch."""
    is_positive = Is[lambda x: x > 0]
    for hint in (
        Annotated[int, "meta"],
        # The legacy spellings are deliberate: they are the special forms the new
        # generic branch must not touch.
        Union[int, str],  # noqa: UP007
        Optional[int],  # noqa: UP007, UP045
        Callable[[int], str],
        Literal[1, 2],
        type[int],
        list[int],
        dict[str, int],
        int,
        Any,
        Annotated[int, is_positive],
    ):
        # Compare with beartype's semantics rather than by identity: plum already
        # normalises `typing.Callable` to `collections.abc.Callable`, which is the
        # same hint. What matters is that the new generic branch changes nothing.
        assert TypeHint(resolve_type_hint(hint)) == TypeHint(hint)

    assert resolve_type_hint(is_positive) is is_positive


def test_no_warning_for_generic_hints(recwarn: pytest.WarningsRecorder) -> None:
    """Registering a generic method must not warn about unresolvable hints."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[int]) -> str:
        return "int"

    assert f(Box[int](1)) == "int"
    assert [w for w in recwarn.list if "Could not" in str(w.message)] == []


def test_generic_defined_in_an_exec_namespace() -> None:
    """A generic whose module is `builtins`, as in a doctest, still dispatches.

    `exec` without a `__name__` leaves `Box.__module__ == "builtins"`, and
    `Box[int]` is then a `typing._GenericAlias` — so a module-name test mistakes it
    for a `typing` special form. The gate keys on `Generic` inheritance instead.
    """
    ns: dict[str, Any] = {}
    exec(
        "from typing import Generic, TypeVar\n"
        'T = TypeVar("T")\n'
        "class Box(Generic[T]):\n"
        "    def __init__(self, v): self.v = v\n",
        ns,
    )
    box = ns["Box"]
    assert box.__module__ == "builtins"
    assert _is_generic_hint(box[int])
    assert not _is_generic_hint(box)

    dispatch = Dispatcher()

    @dispatch
    def f(x: box[int]) -> str:
        return "int"

    @dispatch
    def f(x: box[str]) -> str:
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


def test_parametrised_builtins_still_dispatch() -> None:
    """The pre-existing structural path for builtins is unchanged."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    @dispatch
    def f(x: list[str]) -> str:
        return "list[str]"

    assert f([1]) == "list[int]"
    assert f(["a"]) == "list[str]"


def test_generic_with_annotated_and_union() -> None:
    """A user generic composes with the special forms it sits beside."""
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[int] | Box[str]) -> str:
        return "either"

    @dispatch
    def f(x: Box[float]) -> str:
        return "float"

    assert f(Box[int](1)) == "either"
    assert f(Box[str]("a")) == "either"
    assert f(Box[float](1.0)) == "float"


def test_generic_varargs() -> None:
    dispatch = Dispatcher()

    @dispatch
    def f(*xs: Box[int]) -> str:
        return "ints"

    @dispatch
    def f(*xs: Box[str]) -> str:
        return "strs"

    assert f(Box[int](1), Box[int](2)) == "ints"
    assert f(Box[str]("a")) == "strs"


def test_generic_declared_in_an_exec_namespace_is_cacheable() -> None:
    """Classification must not depend on where the class was written.

    `_is_hint` decides on `__module__`, and a generic declared in an `exec`'d
    namespace -- a doctest among them -- reports `builtins`, the same module as
    `list[int]`. Such a generic used to be classified uncacheable while the identical
    class in an ordinary module was cacheable.
    """
    namespace: dict[str, object] = {}
    exec(  # noqa: S102
        "from typing import Generic, TypeVar\n"
        "T = TypeVar('T')\n"
        "class Exec(Generic[T]):\n"
        "    def __init__(self, value): self.value = value\n",
        namespace,
    )
    cls = namespace["Exec"]
    assert cls.__module__ == "builtins"  # type: ignore[union-attr]
    assert is_cacheable(cls[int])  # type: ignore[index]

    # And the builtin it is now distinguished from stays uncacheable.
    assert not is_cacheable(list[int])


def test_generic_with_an_unhashable_parametrisation_dispatches() -> None:
    """A parametrisation can be unhashable, and must not break the cache key.

    `Box[Annotated[int, {"a": 1}]]` is legal to write, and its `__orig_class__` is
    unhashable. Putting that in the key verbatim makes the key unhashable, so the
    dict lookup in `Function.__call__` raises `TypeError` instead of dispatching.
    """
    dispatch = Dispatcher()

    @dispatch
    def f(x: Box[int]) -> str:
        return "box"

    @dispatch
    def f(x: object) -> str:
        return "object"

    instance = Box[Annotated[int, {"a": 1}]](1)
    assert hash_fails(instance.__orig_class__)

    # Both the cold and the warm path.
    assert f(instance) == "box"
    assert f(instance) == "box"
    # And the ordinary parametrisations are unaffected.
    assert f(Box[int](1)) == "box"
    assert f(Box[str]("a")) == "object"


def hash_fails(value: object) -> bool:
    """Whether `hash(value)` raises, i.e. the value is unhashable."""
    try:
        hash(value)
    except TypeError:
        return True
    return False
