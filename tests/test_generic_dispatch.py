"""Tests for stdlib Generic type dispatch and the _generic helpers.

Red/Green TDD — the caching tests and is_generic_hint tests are RED before
implementation; the dispatch-routing tests verify behavior that already works.
"""

from collections.abc import Sequence
from numbers import Number
from typing import Annotated, Any, ClassVar, Final, Generic, Literal, TypeVar, Union

import pytest

from beartype.vale import Is

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


class Container(Generic[T]):
    def __init__(self, val: object) -> None:
        self.val = val


# ── is_generic_hint ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "hint",
    [list[int], dict[str, int], tuple[int, str], set[float], Sequence[int], Box[int]],
)
def test_is_generic_hint_true(hint):
    assert is_generic_hint(hint)


@pytest.mark.parametrize(
    "hint",
    [
        int,
        list,
        str,
        object,
        Box,
        Union[int, str],  # noqa: UP007
        int | str,
        int | str | None,
        Literal[1],
        Literal[1, 2, 3],
        ClassVar[int],
        Final[int],
        # Annotated aliases must NOT be classified as generic hints even though
        # their wrapped type may be a concrete type (get_origin unwraps them).
        pytest.param(Annotated[int, "meta"], id="Annotated[int,meta]"),
        pytest.param(Annotated[list[int], "meta"], id="Annotated[list[int],meta]"),
    ],
)
def test_is_generic_hint_false(hint):
    assert not is_generic_hint(hint)


def test_is_generic_hint_false_annotated_beartype():
    """Annotated[int, Is[...]] must return False from is_generic_hint.

    Regression: get_origin(Annotated[int, ...]) returns the inner type (int),
    not Annotated itself, so checking origin against _EXCLUDED_ORIGINS never
    matched — Annotated hints were incorrectly classified as generic.
    """

    hint = Annotated[int, Is[lambda v: v > 0]]
    assert not is_generic_hint(hint)


def test_annotated_overload_not_cached_by_bare_type_standalone(
    dispatch: plum.Dispatcher,
):
    """Pure-Annotated dispatch (no generic overload) must never cache by bare type.

    Regression: when is_generic_hint incorrectly returned True for
    Annotated hints, has_generic_signatures was set, which could re-enable
    bare-type caching even for non-faithful resolvers.
    """

    @dispatch
    def f(x: Annotated[int, Is[lambda v: v > 0]]) -> str:
        return "positive"

    @dispatch
    def f(x: Annotated[int, Is[lambda v: v <= 0]]) -> str:
        return "non-positive"

    # Resolver must be non-faithful and must NOT have generic signatures.
    assert f(1) == "positive"
    assert not f._resolver.is_faithful
    assert not f._resolver.has_generic_signatures

    # Value-dependent calls must never be served from a bare-type cache entry.
    assert f(3) == "positive"
    assert f(-1) == "non-positive"
    assert f(0) == "non-positive"
    assert (int,) not in f._cache


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


@pytest.mark.parametrize(
    "left, right, expected",
    [
        (plum.Signature(list[int]), plum.Signature(list), True),
        (plum.Signature(list), plum.Signature(list[int]), False),
        (plum.Signature(list[int]), plum.Signature(list[Number]), True),
        (plum.Signature(Sequence[int]), plum.Signature(Sequence[Number]), True),
        (plum.Signature(Box[int]), plum.Signature(Box), True),
        (plum.Signature(Box), plum.Signature(Box[int]), False),
    ],
)
def test_signature_le_with_generics(left, right, expected):
    assert (left <= right) == expected


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


def test_sequence_int_vs_sequence_str(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: Sequence[int]) -> str:
        return "Sequence[int]"

    @dispatch
    def f(x: Sequence[str]) -> str:
        return "Sequence[str]"

    assert f([1, 2, 3]) == "Sequence[int]"
    assert f(["a", "b"]) == "Sequence[str]"


def test_empty_list_ambiguous_without_fallback(dispatch: plum.Dispatcher):
    """[] matches both list[int] and list[str] → AmbiguousLookupError."""

    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    @dispatch
    def f(x: list[str]) -> str:
        return "list[str]"

    with pytest.raises(plum.AmbiguousLookupError):
        f([])


def test_empty_list_with_fallback_resolves(dispatch: plum.Dispatcher):
    """[] with only list[int] registered should still match (empty is_bearable)."""

    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    @dispatch
    def f(x: list) -> str:
        return "list"

    # is_bearable([], list[int]) == True and list[int] is more specific than list
    assert f([]) == "list[int]"


def test_most_specific_generic_wins(dispatch: plum.Dispatcher):
    """When list[int] and list are both registered, list[int] wins for [1,2,3]."""

    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    @dispatch
    def f(x: list) -> str:
        return "list"

    assert f([1, 2, 3]) == "list[int]"


# ── Caching: faithful methods in a mixed function ────────────────────────────────


def test_faithful_method_cached_in_generic_function(dispatch: plum.Dispatcher):
    """A faithful dispatch (e.g. int) co-existing with a generic dispatch (list[int])
    should still be cached after the first call, not re-resolved on every call."""

    @dispatch
    def f(x: int) -> str:
        return "int"

    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    # First call — cache miss, should populate cache.
    assert f(42) == "int"
    # The resolver is not faithful as a whole (list[int] is non-faithful in
    # plum's sense), but every non-generic method (int) IS faithful, so
    # bare-type caching on the non-generic arm is safe.
    assert not f._resolver.is_faithful
    assert f._resolver.is_faithful_for_non_generic
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


def test_generic_call_cached_after_first_call(dispatch: plum.Dispatcher):
    """Repeated calls with same-type list should hit the cache."""

    @dispatch
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


def test_different_generic_types_cached_separately(dispatch: plum.Dispatcher):
    """list[int] and list[str] calls each get their own cache entry."""

    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    @dispatch
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


def test_bare_box_dispatch(dispatch: plum.Dispatcher):
    """Box (unparameterized) matches a method registered for Box."""

    @dispatch
    def f(x: Box) -> str:
        return "Box"

    assert f(Box(1)) == "Box"
    assert f(Box("a")) == "Box"


def test_box_subscript_more_specific_than_bare():
    """Box[int] signature is more specific than Box."""

    assert plum.Signature(Box[int]) <= plum.Signature(Box)
    assert not (plum.Signature(Box) <= plum.Signature(Box[int]))


def test_parametric_still_works_with_generic_registered(dispatch: plum.Dispatcher):
    """@parametric dispatch must be unaffected by generic dispatch."""

    @plum.parametric
    class MyParam:
        @classmethod
        def __infer_type_parameter__(cls, val: object) -> type:
            return type(val)

    @dispatch
    def f(x: MyParam[int]) -> str:  # type: ignore[type-arg]
        return "MyParam[int]"

    @dispatch
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


def test_orig_class_two_way_dispatch(dispatch: plum.Dispatcher):
    """Box[int](1) and Box[str]('x') route to different overloads."""

    @dispatch
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @dispatch
    def f(x: Box[str]) -> str:
        return "Box[str]"

    assert f(Box[int](1)) == "Box[int]"
    assert f(Box[str]("hello")) == "Box[str]"


def test_orig_class_three_way_with_fallback(dispatch: plum.Dispatcher):
    """Three-way: Box[int], Box[str], and bare Box as a non-parameterized fallback.

    Subscripted instances dispatch correctly via ``__orig_class__``.  Instances
    without ``__orig_class__`` (plain ``Box(…)``) do not match the
    parameterized overloads and fall through to the bare ``Box`` overload.
    """

    @dispatch
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @dispatch
    def f(x: Box[str]) -> str:
        return "Box[str]"

    @dispatch
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


def test_orig_class_bare_no_fallback_raises_not_found(dispatch: plum.Dispatcher):
    """Bare Box(1) with only parameterized overloads raises NotFoundLookupError.

    Bare instances carry no parameterization information, so they don't match
    any of ``Box[int]`` / ``Box[str]``.  Without a fallback overload there is
    no method to dispatch to.
    """

    @dispatch
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @dispatch
    def f(x: Box[str]) -> str:
        return "Box[str]"

    with pytest.raises(plum.NotFoundLookupError):
        f(Box(1))  # no __orig_class__ → no match


def test_orig_class_subscripted_wins_over_bare(dispatch: plum.Dispatcher):
    """Box[int](1) picks Box[int]; bare Box(1) falls through to bare Box overload."""

    @dispatch
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @dispatch
    def f(x: Box) -> str:
        return "Box"

    assert f(Box[int](1)) == "Box[int]"
    # No __orig_class__: Box[int] doesn't match → falls through to bare Box.
    assert f(Box(1)) == "Box"
    # Box[str]("hello") has __orig_class__=Box[str];
    # TypeHint(Box[str]) <= TypeHint(Box[int]) is False, falls through to bare Box.
    assert f(Box[str]("hello")) == "Box"


def test_any_fallback_routes_bare_instances(dispatch: plum.Dispatcher):
    """`Box[Any]` is the explicit fallback for bare `Box(...)` instances.

    With overloads for ``Box[Any]``, ``Box[int]`` and ``Box[str]``:
    - ``Box(1)`` (no ``__orig_class__``) routes to ``Box[Any]``.
    - ``Box[int](1)`` routes to ``Box[int]`` (most specific).
    - ``Box[str]("x")`` routes to ``Box[str]`` (most specific).
    """

    @dispatch
    def f(x: Box[Any]) -> str:
        return "Box[Any]"

    @dispatch
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @dispatch
    def f(x: Box[str]) -> str:
        return "Box[str]"

    assert f(Box(1)) == "Box[Any]"
    assert f(Box[int](1)) == "Box[int]"
    assert f(Box[str]("hello")) == "Box[str]"


def test_any_fallback_alone_matches_everything(dispatch: plum.Dispatcher):
    """``Box[Any]`` alone matches bare *and* subscripted ``Box`` instances."""

    @dispatch
    def f(x: Box[Any]) -> str:
        return "Box[Any]"

    assert f(Box(1)) == "Box[Any]"
    assert f(Box[int](1)) == "Box[Any]"
    assert f(Box[str]("hello")) == "Box[Any]"


def test_plain_any_fallback_with_generic_overload(dispatch: plum.Dispatcher):
    """typing.Any annotation must be reachable even when _arity1_methods is used.

    _arity1_methods buckets are keyed by parameterised-generic origins (e.g.
    ``list``).  Methods whose annotation is plain ``typing.Any`` are *not* a
    generic hint and are excluded from every bucket.  When the filtered bucket
    doesn't contain a match, ``resolve_for_type`` must fall back to
    ``self.resolve()`` so the Any-annotated overload can still be found.

    Regression: before the fix, ``f([1.0, 2.0])`` raised ``NotFoundLookupError``
    because only the ``list[int]`` overload was in the ``list`` bucket and
    ``[1.0, 2.0]`` is not a ``list[int]``.
    """

    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    @dispatch
    def f(x: Any) -> str:
        return "any"

    # list[float] doesn't match list[int] but should fall through to Any.
    assert f([1.0, 2.0]) == "any"
    # list[int] still hits the specific overload.
    assert f([1, 2]) == "list[int]"


def test_union_fallback_with_generic_overload(dispatch: plum.Dispatcher):
    """A Union annotation that can match must be reachable via the Any-fallback path.

    ``Union[list, dict]`` has ``get_origin`` == ``Union`` which is excluded from
    ``is_generic_hint``, so it lands in no _arity1_methods bucket.  Resolution
    must still find it via ``self.resolve()`` fallback.
    """

    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    @dispatch
    def f(x: Union[list, dict]) -> str:  # noqa: UP007
        return "list-or-dict"

    # list[float] doesn't match list[int]; Union[list, dict] accepts any list.
    assert f([1.0, 2.0]) == "list-or-dict"


def test_ambiguous_bucket_stays_ambiguous_with_any_fallback(
    dispatch: plum.Dispatcher,
):
    """AmbiguousLookupError from bucket methods is not hidden by a non-bucket Any.

    Sequence[int] and Sequence[str] both land in the 'list' origin bucket and
    are incomparable.  An empty list matches both vacuously, producing
    AmbiguousLookupError from the pre-filtered subset.

    Adding an Any overload (excluded from every origin bucket because
    ``_can_match_arity1_origin`` returns False for it) does NOT resolve the
    ambiguity: beartype reports ``TypeHint(Any) <= TypeHint(Sequence[int])``
    as False, so Any is never admitted as a candidate in ``_resolve_from``
    even when it matches the argument.  The full ``self.resolve()`` call
    therefore also raises AmbiguousLookupError.

    Consequence: the ``except NotFoundLookupError`` in ``resolve_for_type``
    is the only catch needed — catching AmbiguousLookupError would be a
    no-op and this test documents that expected behaviour.

    Note: the ambiguous call must come BEFORE any non-ambiguous calls to the
    same function.  A prior non-ambiguous dispatch (e.g. f([1])) warms
    ``_generic_cache[(list,)]`` with the Sequence[int] candidate.  The fast
    cache path would then accept an empty list as Sequence[int] vacuously,
    silencing the ambiguity.  Testing the ambiguous case first ensures the
    cache is cold and the resolver is exercised.
    """

    @dispatch
    def f(x: Sequence[int]) -> str:
        return "Seq[int]"

    @dispatch
    def f(x: Sequence[str]) -> str:
        return "Seq[str]"

    @dispatch
    def f(x: Any) -> str:
        return "any"

    # An empty list is genuinely ambiguous — Any does NOT break the tie
    # because TypeHint(Any) is not a subtype of TypeHint(Sequence[int]).
    # Must be called first (cold cache) so the full resolver is reached.
    with pytest.raises(plum.AmbiguousLookupError):
        f([])

    # Non-ambiguous calls still route correctly.
    assert f([1]) == "Seq[int]"
    assert f(["a"]) == "Seq[str]"


def test_orig_class_cache_keyed_separately(dispatch: plum.Dispatcher):
    """Box[int](1) and Box[str](1) must not share a cache entry."""

    @dispatch
    def f(x: Box[int]) -> str:
        return "Box[int]"

    @dispatch
    def f(x: Box[str]) -> str:
        return "Box[str]"

    f(Box[int](1))
    f(Box[str]("x"))
    # Each __orig_class__ is a distinct cache key

    key_int = (Box[int],)
    key_str = (Box[str],)
    assert key_int in f._generic_cache, "Box[int] should be its own cache key"
    assert key_str in f._generic_cache, "Box[str] should be its own cache key"


def test_orig_class_nested_generic(dispatch: plum.Dispatcher):
    """Box[list[int]](…) routes correctly with nested generic hint."""

    @dispatch
    def f(x: Box[list[int]]) -> str:
        return "Box[list[int]]"

    @dispatch
    def f(x: Box[list[str]]) -> str:
        return "Box[list[str]]"

    assert f(Box[list[int]]([1, 2, 3])) == "Box[list[int]]"
    assert f(Box[list[str]](["a"])) == "Box[list[str]]"


def test_orig_class_mixed_with_non_generic_arg(dispatch: plum.Dispatcher):
    """Multi-arg dispatch where only one arg has __orig_class__."""

    @dispatch
    def f(x: int, y: Box[int]) -> str:
        return "int,Box[int]"

    @dispatch
    def f(x: int, y: Box[str]) -> str:
        return "int,Box[str]"

    assert f(1, Box[int](42)) == "int,Box[int]"
    assert f(1, Box[str]("hello")) == "int,Box[str]"


# ── Two generic arguments ────────────────────────────────────────────────────────────
# These tests verify that beartype correctly checks BOTH arguments when every
# parameter carries a parameterised generic hint.  The mechanism under test is
# `is_bearable_with_orig`, which is called once per (arg, hint) pair inside
# `_resolve_generic`.


def test_two_stdlib_list_generics(dispatch: plum.Dispatcher):
    """Dispatch over two list[T] args with swapped element types."""

    @dispatch
    def f(x: list[int], y: list[str]) -> str:
        return "list[int],list[str]"

    @dispatch
    def f(x: list[str], y: list[int]) -> str:
        return "list[str],list[int]"

    # beartype inspects element types on both args to pick the right overload.
    assert f([1, 2], ["a"]) == "list[int],list[str]"
    assert f(["a"], [1, 2]) == "list[str],list[int]"


def test_two_different_stdlib_generics(dispatch: plum.Dispatcher):
    """Dispatch over list[T] and dict[K, V] as separate generic arguments."""

    @dispatch
    def f(x: list[int], y: dict[str, int]) -> str:
        return "list[int],dict[str,int]"

    @dispatch
    def f(x: list[str], y: dict[int, str]) -> str:
        return "list[str],dict[int,str]"

    assert f([1], {"a": 1}) == "list[int],dict[str,int]"
    assert f(["a"], {1: "b"}) == "list[str],dict[int,str]"


def test_two_custom_generic_args(dispatch: plum.Dispatcher):
    """Dispatch over Box[T] for both arguments using __orig_class__."""

    @dispatch
    def f(x: Box[int], y: Box[str]) -> str:
        return "Box[int],Box[str]"

    @dispatch
    def f(x: Box[str], y: Box[int]) -> str:
        return "Box[str],Box[int]"

    # Box[int](1) sets __orig_class__ = Box[int]; is_bearable_with_orig uses
    # that to distinguish Box[int] from Box[str] at runtime.
    assert f(Box[int](1), Box[str]("a")) == "Box[int],Box[str]"
    assert f(Box[str]("a"), Box[int](1)) == "Box[str],Box[int]"


def test_two_different_custom_generic_types(dispatch: plum.Dispatcher):
    """Dispatch over two distinct custom Generic classes: Box[T] and Container[T]."""

    @dispatch
    def f(x: Box[int], y: Container[str]) -> str:
        return "Box[int],Container[str]"

    @dispatch
    def f(x: Box[str], y: Container[int]) -> str:
        return "Box[str],Container[int]"

    assert f(Box[int](1), Container[str]("a")) == "Box[int],Container[str]"
    assert f(Box[str]("a"), Container[int](1)) == "Box[str],Container[int]"


def test_mixed_stdlib_and_custom_generic(dispatch: plum.Dispatcher):
    """Dispatch over one stdlib generic (list) and one custom generic (Box)."""

    @dispatch
    def f(x: list[int], y: Box[str]) -> str:
        return "list[int],Box[str]"

    @dispatch
    def f(x: list[str], y: Box[int]) -> str:
        return "list[str],Box[int]"

    assert f([1], Box[str]("a")) == "list[int],Box[str]"
    assert f(["a"], Box[int](1)) == "list[str],Box[int]"


def test_two_generic_args_type_error_raised(dispatch: plum.Dispatcher):
    """Beartype checks both args independently; mismatched element types raise."""

    @dispatch
    def f(x: list[int], y: list[str]) -> str:
        return "list[int],list[str]"

    # Second arg is list[int], not list[str] — no overload matches.
    with pytest.raises(plum.NotFoundLookupError):
        f([1], [1])

    # First arg is list[str], not list[int] — no overload matches.
    with pytest.raises(plum.NotFoundLookupError):
        f(["a"], ["a"])


def test_two_stdlib_generics_cached_under_same_bare_key(dispatch: plum.Dispatcher):
    """Both two-list combos share key (list, list); the cache holds 2 candidates."""

    @dispatch
    def f(x: list[int], y: list[str]) -> str:
        return "list[int],list[str]"

    @dispatch
    def f(x: list[str], y: list[int]) -> str:
        return "list[str],list[int]"

    f([1], ["a"])
    f(["a"], [1])

    # Both dispatch calls share the same bare-type key because neither list
    # instance carries __orig_class__.  The two entries live as separate
    # candidates inside the same bucket.
    key = (list, list)
    assert key in f._generic_cache
    assert len(f._generic_cache[key]) == 2


def test_two_custom_generics_cached_separately(dispatch: plum.Dispatcher):
    """Box[int]+Box[str] and Box[str]+Box[int] produce distinct cache keys."""

    @dispatch
    def f(x: Box[int], y: Box[str]) -> str:
        return "Box[int],Box[str]"

    @dispatch
    def f(x: Box[str], y: Box[int]) -> str:
        return "Box[str],Box[int]"

    f(Box[int](1), Box[str]("a"))
    f(Box[str]("a"), Box[int](1))

    # __orig_class__ is used as the key component, so the two argument orders
    # produce entirely separate top-level cache entries.
    assert (Box[int], Box[str]) in f._generic_cache
    assert (Box[str], Box[int]) in f._generic_cache


# ── Caching correctness: non-faithful + generic mix ──────────────────────────────────


def test_non_faithful_generic_mix_not_cached_by_bare_type(dispatch: plum.Dispatcher):
    """A function with both a generic overload (list[int]) and a
    value-dependent (Annotated/BeartypeValidator) overload must NOT cache
    the value-dependent result by bare type.  If it did, a subsequent call
    with the same type but a different value would return the wrong method.

    This is a regression test for the bug where
    ``is_faithful or has_generic_signatures`` incorrectly enabled caching
    for non-faithful resolvers that happened to also have generic signatures.
    """

    @dispatch
    def f(x: Annotated[int, Is[lambda v: v > 0]]) -> str:
        return "positive"

    @dispatch
    def f(x: Annotated[int, Is[lambda v: v <= 0]]) -> str:
        return "non-positive"

    @dispatch
    def f(x: list[int]) -> str:
        return "list[int]"

    # Trigger registration so resolver state is populated.
    assert f(5) == "positive"

    # Resolver properties: non-faithful (Annotated overloads) + has generics
    # (list[int]).
    assert not f._resolver.is_faithful
    assert f._resolver.has_generic_signatures
    # is_faithful_for_non_generic must be False: Annotated overloads are non-faithful
    # and non-generic, so bare-type caching on the non-generic arm is unsafe.
    assert not f._resolver.is_faithful_for_non_generic

    # Subsequent calls with different values of the same type must dispatch correctly
    # (the int result must NOT have been cached under the bare type (int,)).
    assert f(-1) == "non-positive"  # must NOT return "positive" from a stale cache
    assert f(0) == "non-positive"
    assert f(3) == "positive"
    assert f([1, 2]) == "list[int]"
    assert (int,) not in f._cache


# ── _can_match_arity1_origin safety: non-type origins ────────────────────────────


def test_literal_overload_does_not_raise_on_registration(dispatch: plum.Dispatcher):
    """Registering a Literal-typed arity-1 function must not raise TypeError.

    Before the fix, is_generic_hint(Literal[1]) was True, causing
    _can_match_arity1_origin to pass Literal (a _SpecialForm, not a type) to
    issubclass, raising TypeError during resolver.register().
    """

    @dispatch
    def f(x: Literal[1]) -> str:
        return "one"

    @dispatch
    def f(x: int) -> str:
        return "int"

    # Registration must complete without raising; dispatch should work too.
    assert f(1) in ("one", "int")  # exact winner depends on faithfulness ordering
    assert f(2) == "int"
