import sys
from typing import Literal

import pytest

import plum
from .util import benchmark


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
    assert len(f._verify_cache[(list,)]) == 2
    assert len(f._verify_cache[(int,)]) == 1


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
