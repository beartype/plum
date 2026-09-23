import sys

import pytest

import plum
from .util import benchmark


def _traced():
    """Whether a line tracer, i.e. `coverage`, is instrumenting this process.

    Tracing inflates a cache *hit* far more than a cache *miss*. A hit is a dozen
    traced Python lines doing almost no work, whereas a miss spends most of its time
    inside `beartype` and C, which the tracer never sees. One full suite run on
    CPython 3.13, in microseconds:

                    hit    miss    ratio
        plain      1.005  27.596    27.4
        --cov      5.160  94.165    18.3

    CI runs every version job under `--cov`, on runners slower than that, where the
    hit inflates further still and the ratio lands just either side of the 4 asserted
    below. The numbers then say more about the tracer than about plum: they fail when
    a change makes a *miss* faster, which is the wrong way round. `Test mypyc wheel`
    runs the suite without `--cov`, as does a plain local `pytest`, so the assertions
    still run somewhere real.
    """
    # Both, because neither alone is enough. `sys.gettrace` catches a plain
    # `settrace` tracer but not coverage from Python 3.12 on, which drives
    # `sys.monitoring` instead and leaves `gettrace` empty; the coverage API catches
    # that but knows nothing about other tracers.
    if sys.gettrace() is not None:
        return True
    try:
        import coverage
    except ImportError:
        return False
    return coverage.Coverage.current() is not None


def assert_cache_performance(f, f_native):
    if _traced():
        # `skip`, not a bare `return`: the coverage jobs run the whole suite under
        # `--cov`, so this would otherwise stop asserting anything there and report
        # nothing about it. A skip says so in the run.
        pytest.skip("a line tracer is attached; see `_traced`")

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

    # Test performance.
    assert_cache_performance(f, f_native)

    # Test cache correctness.
    assert f(1) is None

    @dispatch
    def f(x: int):
        return 1

    assert f(1) == 1


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

    # Since `f` is not faithful, no cache should be accumulated.
    assert f(1) == 1
    assert f([1]) == 2
    assert len(f._cache) == 0
