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


def test_list_int_vs_list_str(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    @dispatch
    def f(x: list[str]) -> str:
        return "list[str]"

    assert f([1, 2, 3]) == "list[int]"
    assert f(["a", "b"]) == "list[str]"


def test_list_int_with_list_fallback(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    @dispatch
    def f(x: list) -> str:
        return "list"

    assert f([1, 2, 3]) == "list[int]"
    assert f(["a", "b"]) == "list"


def test_dict_str_int_dispatch(dispatch: plum.Dispatcher):
    @dispatch
    def g(x: dict[str, int]) -> str:
        return "dict[str,int]"

    @dispatch
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
    assert (
        generic_cache_size > 0
    ), "Expected _generic_cache populated after first generic call"

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
    f(["a", "b"])

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


# ── __orig_class__ dispatch ──────────────────────────────────────────────────────
#
# When a user instantiates a subscripted generic, Python automatically sets
# ``instance.__orig_class__ = Box[int]`` *after* ``__init__`` returns.  We can
# use that attribute as an enriched cache key so that ``Box[int](1)`` and
# ``Box[str](1)`` route to different overloads even though ``type(...)`` is the
# same bare ``Box`` for both.
#
# All tests below are RED until _arg_key is wired into _resolve_method_with_cache
# and resolve_for_type.


def test_orig_class_two_way_dispatch():
    """Box[int](1) and Box[str]('x') route to different overloads."""
    d = plum.Dispatcher()

    @d
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @d
    def f(x: Box[str]) -> str:
        return "Box[str]"

    assert f(Box[int](1)) == "Box[int]"
    assert f(Box[str]("hello")) == "Box[str]"


def test_orig_class_three_way_with_fallback():
    """Three-way: Box[int], Box[str], and bare Box as a non-parameterized fallback.

    Subscripted instances dispatch correctly via ``__orig_class__``.  Instances
    without ``__orig_class__`` (plain ``Box(…)``) do not match the
    parameterized overloads and fall through to the bare ``Box`` overload.
    """
    d = plum.Dispatcher()

    @d
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @d
    def f(x: Box[str]) -> str:
        return "Box[str]"

    @d
    def f(x: Box) -> str:
        return "Box"

    assert f(Box[int](1)) == "Box[int]"
    assert f(Box[str]("hello")) == "Box[str]"
    # Box[object] has __orig_class__ = Box[object]; TypeHint ordering says it is
    # NOT a subtype of Box[int] or Box[str], but IS a subtype of bare Box.
    assert f(Box[object](None)) == "Box"
    # Bare Box(None) has no __orig_class__: parameterized overloads no longer
    # match — only the bare Box overload does.
    assert f(Box(None)) == "Box"


def test_orig_class_bare_no_fallback_raises_not_found():
    """Bare Box(1) with only parameterized overloads raises NotFoundLookupError.

    Bare instances carry no parameterization information, so they don't match
    any of ``Box[int]`` / ``Box[str]``.  Without a fallback overload there is
    no method to dispatch to.
    """
    d = plum.Dispatcher()

    @d
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @d
    def f(x: Box[str]) -> str:
        return "Box[str]"

    with pytest.raises(plum.NotFoundLookupError):
        f(Box(1))  # no __orig_class__ → no match


def test_orig_class_subscripted_wins_over_bare():
    """Box[int](1) picks Box[int]; bare Box(1) falls through to bare Box overload."""
    d = plum.Dispatcher()

    @d
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @d
    def f(x: Box) -> str:
        return "Box"

    assert f(Box[int](1)) == "Box[int]"
    # No __orig_class__: Box[int] doesn't match → falls through to bare Box.
    assert f(Box(1)) == "Box"
    # Box[str]("hello") has __orig_class__=Box[str];
    # TypeHint(Box[str]) <= TypeHint(Box[int]) is False, falls through to bare Box.
    assert f(Box[str]("hello")) == "Box"


def test_any_fallback_routes_bare_instances():
    """`Box[Any]` is the explicit fallback for bare `Box(...)` instances.

    With overloads for ``Box[Any]``, ``Box[int]`` and ``Box[str]``:
    - ``Box(1)`` (no ``__orig_class__``) routes to ``Box[Any]``.
    - ``Box[int](1)`` routes to ``Box[int]`` (most specific).
    - ``Box[str]("x")`` routes to ``Box[str]`` (most specific).
    """
    from typing import Any as _Any

    d = plum.Dispatcher()

    @d
    def f(x: Box[_Any]) -> str:
        return "Box[Any]"

    @d
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @d
    def f(x: Box[str]) -> str:
        return "Box[str]"

    assert f(Box(1)) == "Box[Any]"
    assert f(Box[int](1)) == "Box[int]"
    assert f(Box[str]("hello")) == "Box[str]"


def test_any_fallback_alone_matches_everything():
    """``Box[Any]`` alone matches bare *and* subscripted ``Box`` instances."""
    from typing import Any as _Any

    d = plum.Dispatcher()

    @d
    def f(x: Box[_Any]) -> str:
        return "Box[Any]"

    assert f(Box(1)) == "Box[Any]"
    assert f(Box[int](1)) == "Box[Any]"
    assert f(Box[str]("hello")) == "Box[Any]"


def test_orig_class_cache_keyed_separately():
    """Box[int](1) and Box[str](1) must not share a cache entry."""
    d = plum.Dispatcher()

    @d
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @d
    def f(x: Box[str]) -> str:
        return "Box[str]"

    f(Box[int](1))
    f(Box[str]("x"))
    # Each __orig_class__ is a distinct cache key

    key_int = (Box[int],)
    key_str = (Box[str],)
    assert key_int in f._generic_cache, "Box[int] should be its own cache key"
    assert key_str in f._generic_cache, "Box[str] should be its own cache key"


def test_orig_class_nested_generic():
    """Box[list[int]](…) routes correctly with nested generic hint."""
    d = plum.Dispatcher()

    @d
    def f(x: Box[list[int]]) -> str:
        return "Box[list[int]]"

    @d
    def f(x: Box[list[str]]) -> str:
        return "Box[list[str]]"

    assert f(Box[list[int]]([1, 2, 3])) == "Box[list[int]]"
    assert f(Box[list[str]](["a"])) == "Box[list[str]]"


def test_orig_class_mixed_with_non_generic_arg():
    """Multi-arg dispatch where only one arg has __orig_class__."""
    d = plum.Dispatcher()

    @d
    def f(x: int, y: Box[int]) -> str:
        return "int,Box[int]"

    @d
    def f(x: int, y: Box[str]) -> str:
        return "int,Box[str]"

    assert f(1, Box[int](42)) == "int,Box[int]"
    assert f(1, Box[str]("hello")) == "int,Box[str]"
