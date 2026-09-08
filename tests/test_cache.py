import itertools
import random
import sys
import threading
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Literal

import pytest

import plum
from .util import benchmark
from plum import _function as _function_module
from plum._function import Function
from plum._resolver import resolution_order


def _traced():
    """Whether a tracer is attached, which inflates a cache hit far more than a miss.

    See #315 for the numbers.
    """
    # `sys.gettrace` sees any trace function, including coverage's up to Python 3.13.
    # From 3.14, coverage uses `sys.monitoring` by default and installs no trace
    # function, so ask `coverage` itself as well.
    if sys.gettrace() is not None:
        return True
    try:
        import coverage
    except ImportError:  # pragma: no cover
        return False
    return coverage.Coverage.current() is not None


def assert_cache_performance(f, f_native):
    if _traced():
        pytest.skip("A tracer is attached, which skews the hit/miss timing.")

    # Time the performance of a native call.
    dur_native = benchmark(f_native, (1,), n=250, burn=10)

    def resolve_registrations():
        for f in plum.Function._instances:
            f._resolve_pending_registrations()

    def setup_no_cache():
        plum.clear_all_cache()
        resolve_registrations()

    # Time the performance of a cache miss.
    dur_first = benchmark(f, (1,), n=250, burn=10, setup=setup_no_cache)

    # Time the performance of a cache hit.
    plum.clear_all_cache()
    resolve_registrations()
    dur = benchmark(f, (1,), n=250, burn=10)

    # A cached call should not be more than 50 times slower than a native call.
    assert dur <= 50 * dur_native

    # A first call should not be more than 2000 times slower than a cached call.
    assert dur_first <= 2000 * dur

    # The cached call should be at least 4 times faster than a first call.
    assert dur <= dur_first / 4


@pytest.mark.benchmark
def test_cache_function(dispatch: plum.Dispatcher):
    def f_native(x):
        pass

    @dispatch
    def f(x):
        pass

    @dispatch
    def f(x: int | float):
        pass

    @dispatch
    def f(x: int | float | str):
        pass

    assert_cache_performance(f, f_native)


# This class needs to be in the global scope, otherwise it cannot its methods cannot
# obtains a reference to it.


class A:
    _dispatch = plum.Dispatcher()

    @_dispatch
    def __call__(self, x: int):
        pass

    @_dispatch
    def __call__(self, x: str):
        pass

    @_dispatch
    def go(self, x: int):
        pass

    @_dispatch
    def go(self, x: str):
        pass

    @_dispatch
    def go_again(self, x: int):
        pass

    @_dispatch
    def go_again(self, x: str):
        pass


@pytest.mark.benchmark
def test_cache_class():
    class ANative:
        def __call__(self, x):
            pass

        def go(self, x):
            pass

        def go_again(self, x):
            pass

    a_native = ANative()
    a = A()

    # Test performance of calls.
    assert_cache_performance(a, a_native)

    # Test performance of method calls.
    assert_cache_performance(lambda x: a.go(x), lambda x: a_native.go(x))

    # Test performance of static calls.
    assert_cache_performance(
        lambda x: A.go_again(a, x),
        lambda x: ANative.go_again(a_native, x),
    )


def test_cache_clearing(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int):
        return 1

    @dispatch
    def f(x: float):
        return 2

    assert len(f._cache) == 0
    assert len(f._resolver) == 0

    assert f(1) == 1
    # Check that cache is used.
    assert len(f._cache) == 1
    assert len(f._resolver) == 2

    # Clear via the dispatcher.
    dispatch.clear_cache()
    assert len(f._cache) == 0
    assert len(f._resolver) == 0

    # Run the function again.
    assert f(1) == 1
    assert len(f._cache) == 1
    assert len(f._resolver) == 2

    # Clear via `clear_all_cache`.
    plum.clear_all_cache()
    assert len(f._cache) == 0
    assert len(f._resolver) == 0

    # Run the function one last time.
    assert f(1) == 1
    assert len(f._cache) == 1
    assert len(f._resolver) == 2


def test_cache_unfaithful(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int):
        return 1

    @dispatch
    def f(x: list[int]):
        return 2

    # Since `f` is not cacheable, no cache should be accumulated.
    assert f(1) == 1
    assert f([1]) == 2
    assert len(f._cache) == 0


def test_cache_type_x(dispatch: plum.Dispatcher):
    """Test that dispatch on `type[X]` is cached per class, also when added later."""

    @dispatch
    def f(x: object):
        return "object"

    assert f(int) == "object"
    assert f(str) == "object"
    # `f` is faithful, so both calls share the entry for `type`.
    assert set(f._cache) == {(type,)}

    @dispatch
    def f(x: type[int]):
        return "type[int]"

    assert f(int) == "type[int]"
    assert f(str) == "object"
    # One entry per class, and the entry for `type` is gone.
    assert len(f._cache) == 2
    assert (type,) not in f._cache


def test_literal_dispatch_is_cached(dispatch):
    """Test that a function dispatching on `Literal` caches one entry per value."""

    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: Literal[2]):
        return "two"

    @dispatch
    def f(x: int):
        return "int"

    f._resolve_pending_registrations()
    assert f._resolver.is_cacheable and not f._resolver.is_faithful
    assert len(f._cache) == 0

    assert f(1) == "one"
    assert f(2) == "two"
    assert f(3) == "int"
    # Distinct literal values must not collide: one entry each.
    assert len(f._cache) == 3
    # And the cached answers must still be the right ones.
    assert (f(1), f(2), f(3)) == ("one", "two", "int")
    assert len(f._cache) == 3


def test_literal_dispatch_keeps_bool_and_int_apart(dispatch):
    """Test that `True` and `1`, which are equal, are cached separately."""

    @dispatch
    def f(x: Literal[True]):
        return "true"

    @dispatch
    def f(x: int):
        return "int"

    assert f(True) == "true"
    assert f(1) == "int"
    assert f(0) == "int"
    # `True == 1`, so only the type slot of the key keeps these entries apart.
    assert len(f._cache) == 3


def test_literal_dispatch_unhashable_argument(dispatch):
    """Test that an unhashable argument does not make the cache key raise."""

    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: object):
        return "object"

    assert f([1, 2]) == "object"
    assert f(1) == "one"


def test_literal_and_type_dispatch_mixed(dispatch):
    """Test caching of a function that dispatches on both `Literal` and `type[X]`."""
    from plum._type import KeyPart

    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: type[int]):
        return "type[int]"

    @dispatch
    def f(x: object):
        return "object"

    f._resolve_pending_registrations()
    assert f._resolver.cache_spec == {KeyPart.IDENTITY, KeyPart.VALUE}

    assert f(1) == "one"
    assert f(int) == "type[int]"
    assert f(2) == "object"
    assert f(str) == "object"
    assert len(f._cache) == 4


def test_literal_dispatch_subclass_with_untrustworthy_equality(dispatch):
    """Test that a subclass with a non-transitive `__eq__` is dispatched correctly."""

    class W(int):
        def __hash__(self):
            return 0

        def __eq__(self, other):
            if type(other) is W:
                return True
            return int.__eq__(self, other)

    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: int):
        return "int"

    assert f(W(1)) == "one"
    assert f(W(2)) == "int"
    # And in the other warm-up order.
    f.clear_cache()
    assert f(W(2)) == "int"
    assert f(W(1)) == "one"


def test_literal_dispatch_and_identity_for_subclasses(dispatch):
    """Test dispatch and per-object caching of an instance of a subclass."""

    class MyInt(int):
        pass

    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: int):
        return "int"

    assert f(MyInt(1)) == "one"
    assert f(MyInt(2)) == "int"
    assert f(MyInt(1)) == "one"
    assert len(f._cache) == 3


def test_literal_dispatch_cache_is_bounded(dispatch):
    """Test that the cache of a function dispatching on `Literal` is limited."""
    from plum._function import _VALUE_CACHE_LIMIT

    @dispatch
    def f(x: Literal["ready"]):
        return "ready"

    @dispatch
    def f(x: str):
        return "other"

    for i in range(_VALUE_CACHE_LIMIT + 100):
        assert f(f"v{i}") == "other"

    assert len(f._cache) == _VALUE_CACHE_LIMIT
    # Beyond the limit, resolution still gives the right answer.
    assert f("ready") == "ready"
    assert f("v0") == "other"
    assert len(f._cache) == _VALUE_CACHE_LIMIT


def test_verify_cache_narrows_the_methods_considered(dispatch):
    """Test that the verify cache holds only the methods that could match."""

    @dispatch
    def f(x: list[int]):
        return "list[int]"

    @dispatch
    def f(x: list[str]):
        return "list[str]"

    @dispatch
    def f(x: int):
        return "int"

    assert f([1]) == "list[int]"
    assert f(["a"]) == "list[str]"
    assert f(1) == "int"

    # Uncacheable, so no method is memoised.
    assert len(f._cache) == 0
    # But the methods that could possibly match are, bucketed by bare types.
    assert set(f._verify_cache) == {(list,), (int,)}
    # A `list` argument can never match `int`, and vice versa.
    assert len(f._verify_cache[(list,)][0]) == 2
    assert len(f._verify_cache[(int,)][0]) == 1


def test_verify_cache_clearing(dispatch: plum.Dispatcher):
    """Test that registering a method and clearing the cache clear the verify cache."""

    @dispatch
    def f(x: list[int]):
        return "list[int]"

    assert f([1]) == "list[int]"

    @dispatch
    def f(x: list[str]):
        return "list[str]"

    # The new method must be considered for `list` arguments.
    assert f(["a"]) == "list[str]"

    dispatch.clear_cache()
    assert f._verify_cache is None
    assert f([1]) == "list[int]"
    plum.clear_all_cache()
    assert f._verify_cache is None


@pytest.mark.incompatible_with_mypyc
def test_verify_bucket_overtaken_by_a_clear_is_not_cached(monkeypatch, dispatch):
    """A verify-cache bucket build overtaken by a `clear_cache` must not poison a
    *new* `_verify_cache` dict with a bucket narrowed from the superseded method
    set. `_build_verify_bucket` must store into the `cache` dict `_resolve_miss`
    captured before resolving, not into whatever `self._verify_cache` happens to
    be by the time the build finishes. See GitHub issue #274 for the analogous
    method-cache race this mirrors.
    """

    @dispatch
    def f(x: list[int]):
        return "v1"

    f._resolve_pending_registrations()

    building, invalidated, parked_once = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    original = _function_module.resolution_order

    def parked(methods):
        # Narrowing (`might_match`) already ran against the pre-registration
        # method set before this is called; park here, before the store, which
        # is where the clear lands. Only the first call parks -- later calls in
        # this test (warming the new bucket) must run straight through.
        out = original(methods)
        if not parked_once.is_set():
            parked_once.set()
            building.set()
            assert invalidated.wait(5), "the clear never landed"
        return out

    monkeypatch.setattr(_function_module, "resolution_order", parked)
    with ThreadPoolExecutor(1) as pool:
        # `[1]` and `["a"]` below share a runtime type (`list`), so both key the
        # verify cache under the same bucket, `(list,)`.
        call = pool.submit(f, [1])
        assert building.wait(5), "the parked thread never reached the park"

        @dispatch
        def f(x: list[str]):  # noqa: F811
            return "v2"

        f._resolve_pending_registrations()
        assert f._verify_cache is None  # Cleared by the registration.

        # Warm a *new* `(list,)` bucket, correctly narrowed to both methods now
        # that the registration has landed.
        assert f(["a"]) == "v2"
        assert len(f._verify_cache[(list,)][0]) == 2

        invalidated.set()
        call.result(5)

    # The parked build, narrowed to only the superseded `list[int]` method, must
    # not have overwritten the freshly warmed two-method bucket.
    assert len(f._verify_cache[(list,)][0]) == 2
    assert f(["a"]) == "v2"


def test_verify_cache_preserves_ambiguity_and_precedence(dispatch):
    """Test that narrowing preserves ambiguity and its resolution by precedence."""

    @dispatch
    def f(x: list[int], y: object):
        return 1

    @dispatch
    def f(x: object, y: list[int]):
        return 2

    @dispatch(precedence=1)
    def g(x: list[int], y: object):
        return 1

    @dispatch
    def g(x: object, y: list[int]):
        return 2

    with pytest.raises(plum.AmbiguousLookupError):
        f([1], [1])
    assert g([1], [1]) == 1


def test_verify_cache_preserves_not_found(dispatch):
    """Test that a lookup error lists all methods, not only the narrowed ones."""

    @dispatch
    def f(x: list[int]):
        return 1

    @dispatch
    def f(x: tuple[int, ...]):
        return 2

    with pytest.raises(plum.NotFoundLookupError) as e:
        f(["a"])
    assert len(e.value.methods) == 2


def test_verify_cache_handles_varargs_and_arities(dispatch):
    """Test that narrowing respects arities and varargs."""

    @dispatch
    def f(x: int, *xs: list[int]):
        return "varargs"

    @dispatch
    def f(x: int):
        return "one"

    @dispatch
    def f(x: int, y: int):
        return "two"

    assert f(1) == "one"
    assert f(1, 2) == "two"
    assert f(1, [1]) == "varargs"
    assert f(1, [1], [2]) == "varargs"


# When a bucket can be put in resolution order, the first method that matches is the
# one full resolution would select, so the call can return on it.

_mro_dispatch = plum.Dispatcher()


class _MroBase:
    def f(self, x):
        return "base"


class _MroSub(_MroBase):
    @_mro_dispatch
    def f(self, x: list[int]):
        return "sub"


def test_verify_cache_orders_a_comparable_bucket(dispatch):
    @dispatch
    def f(x: list):
        return "list"

    @dispatch
    def f(x: list[int]):
        return "list[int]"

    assert f([1]) == "list[int]"
    assert f([1]) == "list[int]"
    assert f(["a"]) == "list"

    methods, entries, first_wins = f._verify_cache[(list,)]
    assert first_wins

    # `methods` stays in registration order: `Resolver.resolve` and the error
    # messages both want it that way.
    assert [m.signature.types for m in methods] == [(list,), (list[int],)]

    # The *ordered* list is what the first-match fast path walks, and it is what the
    # `first_wins` claim rests on. Assert the ordering itself, most specific first,
    # rather than inferring it from the bucket.
    ordered = resolution_order(methods)
    assert ordered is not None
    assert [m.signature.types for m in ordered] == [(list[int],), (list,)]
    # And the fast path walks exactly that many candidates, in that order.
    assert len(entries) == len(ordered)


def test_verify_cache_does_not_order_an_incomparable_bucket(dispatch):
    @dispatch
    def f(x: list[int]):
        return "list[int]"

    @dispatch
    def f(x: list[str]):
        return "list[str]"

    assert f([1]) == "list[int]"
    # Neither signature is below the other, and the empty list matches both, so the
    # bucket cannot return on a first match.
    assert not f._verify_cache[(list,)][2]
    with pytest.raises(plum.AmbiguousLookupError):
        f([])


def test_verify_cache_settles_an_unordered_bucket_on_a_unique_match(dispatch):
    @dispatch
    def f(x: list[int]):
        return "list[int]"

    @dispatch
    def f(x: list[str]):
        return "list[str]"

    # An unordered bucket can still settle a call that matches exactly one of its
    # methods: that method is the only candidate full resolution can collect.
    assert f([1]) == "list[int]"
    assert f(["a"]) == "list[str]"
    assert not f._verify_cache[(list,)][2]

    # Several matches fall through to full resolution, which finds the ambiguity.
    with pytest.raises(plum.AmbiguousLookupError):
        f([])
    # So does no match at all, which reports every method, not just the bucket.
    with pytest.raises(plum.NotFoundLookupError) as e:
        f([1.0])
    assert len(e.value.methods) == 2


@pytest.mark.incompatible_with_mypyc
def test_verify_cache_fallback_resolves_against_the_current_methods(
    monkeypatch, dispatch
):
    """A call that falls all the way through the verify-cache's fast paths (no
    match, or several with no order between them) must resolve against the
    CURRENT method set, not the narrowed candidate list from when the bucket was
    last (re)built. `resolve_method` flushes a concurrent registration to the
    resolver internally; a stale narrowed list threaded into it regardless would
    have `Resolver.resolve` see only the old candidates, missing exactly the
    method the flush just added, and raise `NotFoundLookupError` even though the
    call is now resolvable.
    """

    @dispatch
    def f(x: list[int]):
        return "list[int]"

    @dispatch
    def f(x: list[str]):
        return "list[str]"

    # Warm an incomparable, two-method bucket for `list` arguments.
    assert f([1]) == "list[int]"
    assert f(["a"]) == "list[str]"
    assert not f._verify_cache[(list,)][2]

    reached_fallback, registered = threading.Event(), threading.Event()
    original, target = Function.resolve_method, f

    def parked(self, *args, **kw_args):
        if self is target:
            reached_fallback.set()
            # Park right before the fallback call, before the registration below
            # has landed -- exactly the window the bug lived in.
            assert registered.wait(5), "the registration never landed"
        return original(self, *args, **kw_args)

    monkeypatch.setattr(Function, "resolve_method", parked)
    with ThreadPoolExecutor(1) as pool:
        # A list of floats matches neither registered method: falls through to
        # the fallback, past both fast paths.
        call = pool.submit(f, [1.0])
        assert reached_fallback.wait(5), "the parked thread never reached the fallback"

        @dispatch
        def f(x: list[float]):  # noqa: F811
            return "list[float]"

        f._resolve_pending_registrations()
        registered.set()

        assert call.result(5) == "list[float]"


def test_verify_cache_ordering_ignores_precedence(dispatch):
    @dispatch(precedence=5)
    def f(x: list):
        return "list"

    @dispatch
    def f(x: list[int]):
        return "list[int]"

    # A fully comparable bucket is never ambiguous, so precedence never gets a say:
    # specificity decides, exactly as in full resolution.
    assert f([1]) == "list[int]"
    assert f([1]) == "list[int]"
    assert f._verify_cache[(list,)][2]


def test_verify_cache_orders_equally_specific_methods_by_registration(dispatch):
    @dispatch(precedence=1)
    def f(x: list[int]):
        return "first"

    @dispatch
    def f(x: list[int]):
        return "second"

    # The two signatures are below each other but not equal, since they differ in
    # precedence. Full resolution keeps the last registered one, and so must the
    # ordering, cold and warm.
    assert f([1]) == "second"
    assert f([1]) == "second"
    assert f._verify_cache[(list,)][2]
    assert f._resolver.resolve(([1],)).implementation([1]) == "second"


def test_verify_cache_leaves_a_large_bucket_unordered(dispatch):
    hints = [
        list[int],
        list[str],
        list[bool],
        list[float],
        list[bytes],
        list[complex],
        list[frozenset],
        list[tuple],
        list[dict],
        list[set],
        list[object],
    ]
    f = None
    for i, hint in enumerate(hints):

        def impl(x, _i=i):
            return _i

        impl.__name__ = "big"
        f = dispatch.multi(plum.Signature(hint))(impl)

    # Ordering is quadratic in the size of the bucket, so a large one is left to the
    # unique-match path, which resolves it exactly as full resolution does.
    assert len(f.methods) > 10
    assert f([1]) == 0
    assert not f._verify_cache[(list,)][2]
    assert f(["a"]) == 1


def test_verify_cache_first_match_preserves_the_mro_fallback():
    # `["a"]` lands in the same bucket as `[1]` but matches nothing in it, so the
    # first-match path has to fall through to the walk up the MRO.
    sub = _MroSub()
    assert sub.f([1]) == "sub"
    assert sub.f(["a"]) == "base"
    assert sub.f(["a"]) == "base"


# A differential fuzz test for the verify cache. Random method sets over uncacheable
# hints are dispatched over a corpus of values, and every outcome is compared against
# full resolution over all methods, cold and warm. Whatever a bucket does, it has to
# agree with the resolver it stands in for.

_FUZZ_HINTS = (
    list[int],
    list[str],
    list[object],
    list,
    tuple[int, ...],
    dict[str, int],
    Iterable[int],
    list[int] | int,
    Literal[1],
    int,
    object,
)

# Beartype checks a container by sampling an element, so a heterogeneous container
# would make `match` itself random and the comparison meaningless. Every container
# here is homogeneous.
_FUZZ_VALUES = (
    [],
    [1],
    [1, 2],
    ["a"],
    [[1]],
    (1, 2),
    (),
    {"a": 1},
    {"a": "b"},
    1,
    2,
    "a",
    object(),
)


def _fuzz_function(rng):
    """Build a function from a random set of methods over `_FUZZ_HINTS`.

    Returns the function, a map from implementation to the index of the method that
    implements it, and the arities the methods were built for.
    """
    impls = {}
    f = None
    for i in range(rng.randint(1, 4)):

        def impl(*args, _i=i):
            return _i

        impl.__name__ = "fuzzed"
        types = [rng.choice(_FUZZ_HINTS) for _ in range(rng.randint(1, 2))]
        varargs = rng.choice(_FUZZ_HINTS) if rng.random() < 0.2 else plum.Missing
        signature = plum.Signature(
            *types, varargs=varargs, precedence=rng.choice((0, 0, 1))
        )
        if f is None:
            f = plum.Function(impl)
        f.register(impl, signature=signature, precedence=None)
        impls[impl] = i
    f._resolve_pending_registrations()
    return f, impls


def _resolved_index(f, args, impls):
    """The index of the method full resolution selects, using no cache at all."""
    return impls[f._resolver.resolve(args).implementation]


def _outcome(call, impls):
    """Run `call` and reduce whatever it does to a comparable value."""
    try:
        return ("value", call())
    except plum.AmbiguousLookupError as e:
        return ("ambiguous", tuple(sorted(impls[m.implementation] for m in e.methods)))
    except plum.NotFoundLookupError as e:
        return ("not found", tuple(sorted(impls[m.implementation] for m in e.methods)))


def test_verify_cache_differential_fuzz():
    rng = random.Random(20240611)
    uncacheable = 0

    for _ in range(300):
        f, impls = _fuzz_function(rng)
        uncacheable += not f._resolver.is_cacheable

        for n in (1, 2, 3):
            for args in itertools.product(_FUZZ_VALUES, repeat=n):
                if n > 1 and rng.random() > 0.15:
                    continue

                # The reference: full resolution over every method, no cache at all.
                reference = _outcome(partial(_resolved_index, f, args, impls), impls)

                # Cold: every call rebuilds the bucket from scratch.
                f.clear_cache(reregister=False)
                cold = _outcome(partial(f, *args), impls)
                # Warm: the bucket built by the call above is reused.
                warm = _outcome(partial(f, *args), impls)

                assert cold == reference, (args, f.methods)
                assert warm == reference, (args, f.methods)

    # The fast paths under test only run for an uncacheable resolver, so the corpus
    # has to actually produce those.
    assert uncacheable > 200


class _PropertyLiar:
    """Claims to be a `list` through a `__class__` property if `pretend`."""

    def __init__(self, pretend):
        self.pretend = pretend

    @property
    def __class__(self):  # noqa: PLW3201
        return list if self.pretend else _PropertyLiar

    def __len__(self):
        return 1

    def __getitem__(self, i):
        return 1


class _GetattributeLiar:
    """Claims to be a `list` through `__getattribute__` if `pretend`."""

    def __init__(self, pretend):
        self.pretend = pretend

    def __getattribute__(self, name):
        if name == "__class__" and object.__getattribute__(self, "pretend"):
            return list
        return object.__getattribute__(self, name)

    def __len__(self):
        return 1

    def __getitem__(self, i):
        return 1


@pytest.mark.parametrize("liar", [_PropertyLiar, _GetattributeLiar])
@pytest.mark.parametrize("hint", [list, list[int]])
def test_verify_cache_ignores_class_liars(dispatch, liar, hint):
    """Test that the verify cache does not depend on what `__class__` returns."""

    @dispatch
    def f(x: hint):
        return "list"

    @dispatch
    def f(x: dict[str, int]):  # Makes `f` uncacheable.
        return "dict"

    @dispatch
    def f(x: object):
        return "object"

    # Same runtime type, but only the second claims to be a `list`.
    assert f(liar(False)) == "object"
    assert f(liar(True)) == "list"


def test_verify_cache_is_bounded(dispatch):
    """Test that the verify cache stops growing at the cap, with dispatch unchanged."""
    from plum._function import _VERIFY_CACHE_LIMIT

    @dispatch
    def f(x: list[int], y: object):
        return "list[int]"

    @dispatch
    def f(x: object, y: object):
        return "object"

    # More distinct type pairs than the cap allows.
    values = [type(f"B{i}", (), {})() for i in range(_VERIFY_CACHE_LIMIT + 50)]
    for v in values:
        assert f(v, 1) == "object"

    assert len(f._verify_cache) == _VERIFY_CACHE_LIMIT

    assert f([1], 1) == "list[int]"


def test_verify_cache_is_not_allocated_for_cacheable_functions(dispatch):
    """Test that a cacheable function does not allocate a verify cache."""

    @dispatch
    def f(x: int):
        return "int"

    assert f(1) == "int"
    assert f._verify_cache is None


def test_matchers_are_shared_across_verify_cache_buckets(dispatch):
    # A matcher is fixed by the signature and the arity, but buckets are keyed on the
    # runtime types, so without sharing every bucket binds its own copy per method.
    @dispatch
    def f(x: list[int], y: object):
        return "li"

    @dispatch
    def f(x: list[str], y: object):
        return "ls"

    @dispatch
    def f(x: object, y: object):
        return "o"

    class Mk:
        pass

    for i in range(40):
        kind = type(f"T{i}", (Mk,), {})
        f([1], kind())
        f(["a"], kind())

    buckets = list(f._verify_cache.values())
    assert len(buckets) == 40
    matchers = [entry[0] for (_methods, entries, _fw) in buckets for entry in entries]
    assert len(matchers) == 120
    # One per (signature, arity), not one per (bucket, method).
    assert len({id(m) for m in matchers}) == 3


def test_default_args_copy_does_not_inherit_a_stale_matcher(dispatch):
    # `append_default_args` copies a signature and then drops its last type, so a
    # matcher carried across the copy would answer for the original's arity.
    from copy import copy as shallow_copy

    from plum._signature import Signature, _matcher
    from plum._util import Missing

    s = Signature(list, int)
    assert _matcher(s, 2)(([1], 2)) is True
    assert s._matchers is not None  # Warmed.

    c = shallow_copy(s)
    assert c._matchers is None  # The copy starts cold.
    c.varargs = Missing
    c.types = c.types[:-1]  # Exactly what `append_default_args` does.
    assert _matcher(c, 1)(([1],)) is True  # Answers for the copy's arity ...
    assert _matcher(c, 2)(([1], 2)) is False  # ... and rejects the original's.

    # And end to end, through the dispatcher that builds those copies.
    @dispatch
    def f(x: list[int], y: int = 0):
        return ("li", y)

    assert f([1], 5) == ("li", 5)
    assert f([1]) == ("li", 0)
    assert f([1], 5) == ("li", 5)  # Warm.
    assert f([1]) == ("li", 0)
