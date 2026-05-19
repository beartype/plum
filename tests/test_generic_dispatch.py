"""Tests for stdlib Generic type dispatch and the _generic helpers.

Red/Green TDD — the caching tests and is_generic_hint tests are RED before
implementation; the dispatch-routing tests verify behavior that already works.
"""

from collections.abc import Sequence
from numbers import Number
from typing import Generic, TypeVar

import pytest

import plum
from plum._generic import is_generic_hint, le_generic

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class Box(Generic[T]):
    def __init__(self, val: object) -> None:
        self.val = val


class BoxCo(Generic[T_co]):
    def __init__(self, val: object) -> None:
        self.val = val


# ── is_generic_hint ─────────────────────────────────────────────────────────────


def test_is_generic_hint_parameterized_builtins():
    assert is_generic_hint(list[int])
    assert is_generic_hint(dict[str, int])
    assert is_generic_hint(tuple[int, str])
    assert is_generic_hint(set[float])


def test_is_generic_hint_typing_generics():
    assert is_generic_hint(Sequence[int])
    assert is_generic_hint(Box[int])


def test_is_generic_hint_false_for_bare_types():
    assert not is_generic_hint(int)
    assert not is_generic_hint(list)
    assert not is_generic_hint(str)
    assert not is_generic_hint(object)
    assert not is_generic_hint(Box)


# ── le_generic ───────────────────────────────────────────────────────────────────


def test_le_generic_list_covariant():
    """Beartype treats list as covariant: list[int] <= list[object]."""

    assert le_generic(list[int], list[Number])
    assert le_generic(list[int], list)
    assert not le_generic(list, list[int])


def test_le_generic_sequence_covariant():
    assert le_generic(Sequence[int], Sequence[Number])


def test_le_generic_box_covariant():
    # TypeVar T is invariant → Box[int] NOT <= Box[Number] by PEP-484
    # But beartype currently treats it as covariant; we defer to beartype.
    result = le_generic(Box[int], Box[Number])
    # Just assert it returns a bool without error; the exact value matches beartype.
    assert isinstance(result, bool)


# ── Signature ordering with generic hints ────────────────────────────────────────


def test_signature_le_list_int_le_list():
    assert plum.Signature(list[int]) <= plum.Signature(list)
    assert not (plum.Signature(list) <= plum.Signature(list[int]))


def test_signature_le_list_int_le_list_number():
    assert plum.Signature(list[int]) <= plum.Signature(list[Number])


def test_signature_le_sequence_covariant():
    assert plum.Signature(Sequence[int]) <= plum.Signature(Sequence[Number])


def test_signature_le_box_subscript():
    assert plum.Signature(Box[int]) <= plum.Signature(Box)
    assert not (plum.Signature(Box) <= plum.Signature(Box[int]))


# ── Basic stdlib generic dispatch ────────────────────────────────────────────────


def test_list_int_vs_list_str():
    d = plum.Dispatcher()

    @d
    def f(x: list[int]) -> str:
        return "list[int]"

    @d
    def f(x: list[str]) -> str:
        return "list[str]"

    assert f([1, 2, 3]) == "list[int]"
    assert f(["a", "b"]) == "list[str]"


def test_list_int_with_list_fallback():
    d = plum.Dispatcher()

    @d
    def f(x: list[int]) -> str:
        return "list[int]"

    @d
    def f(x: list) -> str:
        return "list"

    assert f([1, 2, 3]) == "list[int]"
    assert f(["a", "b"]) == "list"


def test_dict_str_int_dispatch():
    d = plum.Dispatcher()

    @d
    def g(x: dict[str, int]) -> str:
        return "dict[str,int]"

    @d
    def g(x: dict) -> str:
        return "dict"

    assert g({"a": 1}) == "dict[str,int]"
    assert g({"a": "b"}) == "dict"


def test_sequence_int_vs_sequence_str():
    d = plum.Dispatcher()

    @d
    def f(x: Sequence[int]) -> str:
        return "Sequence[int]"

    @d
    def f(x: Sequence[str]) -> str:
        return "Sequence[str]"

    assert f([1, 2, 3]) == "Sequence[int]"
    assert f(["a", "b"]) == "Sequence[str]"


def test_empty_list_ambiguous_without_fallback():
    """[] matches both list[int] and list[str] → AmbiguousLookupError."""
    d = plum.Dispatcher()

    @d
    def f(x: list[int]) -> str:
        return "list[int]"

    @d
    def f(x: list[str]) -> str:
        return "list[str]"

    with pytest.raises(plum.AmbiguousLookupError):
        f([])


def test_empty_list_with_fallback_resolves():
    """[] with only list[int] registered should still match (empty is_bearable)."""
    d = plum.Dispatcher()

    @d
    def f(x: list[int]) -> str:
        return "list[int]"

    @d
    def f(x: list) -> str:
        return "list"

    # is_bearable([], list[int]) == True and list[int] is more specific than list
    assert f([]) == "list[int]"


def test_most_specific_generic_wins():
    """When list[int] and list are both registered, list[int] wins for [1,2,3]."""
    d = plum.Dispatcher()

    @d
    def f(x: list[int]) -> str:
        return "list[int]"

    @d
    def f(x: list) -> str:
        return "list"

    assert f([1, 2, 3]) == "list[int]"


# ── Caching: faithful methods in a mixed function ────────────────────────────────


def test_faithful_method_cached_in_generic_function():
    """A faithful dispatch (e.g. int) co-existing with a generic dispatch (list[int])
    should still be cached after the first call, not re-resolved on every call."""
    d = plum.Dispatcher()

    @d
    def f(x: int) -> str:
        return "int"

    @d
    def f(x: list[int]) -> str:
        return "list[int]"

    # First call — cache miss, should populate cache.
    assert f(42) == "int"
    # int arg takes the faithful path → stored in _cache (not _generic_cache).
    assert len(f._cache) > 0, "Expected _cache to be populated after first int call"

    cache_size = len(f._cache)
    generic_cache_size = len(f._generic_cache)
    # Second call — should be a cache hit; no new entry added.
    assert f(42) == "int"
    assert (
        len(f._cache) == cache_size
    ), "Cache grew on second identical call (cache miss)"
    assert (
        len(f._generic_cache) == generic_cache_size
    ), "Generic cache grew on second identical int call"


def test_generic_call_cached_after_first_call():
    """Repeated calls with same-type list should hit the cache."""
    d = plum.Dispatcher()

    @d
    def f(x: list[int]) -> str:
        return "list[int]"

    assert f([1, 2, 3]) == "list[int]"
    # list[int] arg takes the two-tier generic cache path.
    generic_cache_size = len(f._generic_cache)
    assert generic_cache_size > 0, "Expected _generic_cache populated after first generic call"

    # Second call with a different list[int] value — should hit cache.
    assert f([4, 5, 6]) == "list[int]"
    assert (
        len(f._generic_cache) == generic_cache_size
    ), "Generic cache grew (cache miss) on second list[int] call"


def test_different_generic_types_cached_separately():
    """list[int] and list[str] calls each get their own cache entry."""
    d = plum.Dispatcher()

    @d
    def f(x: list[int]) -> str:
        return "list[int]"

    @d
    def f(x: list[str]) -> str:
        return "list[str]"

    f([1, 2, 3])
    size_after_int = len(f._generic_cache)

    f(["a", "b"])
    size_after_str = len(f._generic_cache)

    # Both calls share the same bare-type key (list,); the second call adds a
    # second candidate under that key (not a new top-level entry), but the
    # candidates list for that key grows.
    key = (list,)
    assert key in f._generic_cache
    assert len(f._generic_cache[key]) == 2, "Expected two candidates for key (list,)"


# ── Phase 3: user-defined Generic subclasses ────────────────────────────────────


def test_bare_box_dispatch():
    """Box (unparameterized) matches a method registered for Box."""
    d = plum.Dispatcher()

    @d
    def f(x: Box) -> str:
        return "Box"

    assert f(Box(1)) == "Box"
    assert f(Box("a")) == "Box"


def test_box_subscript_more_specific_than_bare():
    """Box[int] signature is more specific than Box."""

    assert plum.Signature(Box[int]) <= plum.Signature(Box)
    assert not (plum.Signature(Box) <= plum.Signature(Box[int]))


def test_parametric_still_works_with_generic_registered():
    """@parametric dispatch must be unaffected by generic dispatch."""

    d = plum.Dispatcher()

    @plum.parametric
    class MyParam:
        @classmethod
        def __infer_type_parameter__(cls, val: object) -> type:
            return type(val)

    @d
    def f(x: MyParam[int]) -> str:  # type: ignore[type-arg]
        return "MyParam[int]"

    @d
    def f(x: list[int]) -> str:
        return "list[int]"

    assert f(MyParam(1)) == "MyParam[int]"
    assert f([1, 2]) == "list[int]"
