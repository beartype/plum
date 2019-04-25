# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Dispatcher
from . import eq, le, benchmark


def test_cache():
    # Test performance.
    dispatch = Dispatcher()

    def f_native(x): return None

    @dispatch(object)
    def f(x):
        return 1

    dur_native = benchmark(f_native, (1,))
    dur_plum_first = benchmark(f, (1,), n=1)
    dur_plum = benchmark(f, (1,))

    # A cached call should not be more than 30 times slower than a native call.
    yield le, dur_plum, 30 * dur_native, 'compare native'

    # A first call should not be more than 200 times slower than a first call.
    yield le, dur_plum_first, 200 * dur_plum, 'compare first'

    # The cached call should be at least 20 times faster than a first call.
    yield le, dur_plum, dur_plum_first / 20, 'cache performance'

    # Test cache correctness.
    yield eq, f(1), 1, 'cache correctness 1'

    @dispatch(int)
    def f(x): return 2

    yield eq, f(1), 2, 'cache correctness 2'


def test_cache_clearing():
    dispatch = Dispatcher()

    @dispatch(object)
    def f(x):
        return 1

    dur1 = benchmark(f, (1,), n=1)
    dispatch.clear_cache()

    # Check that cache is cleared.
    yield eq, len(f.methods), 0
    yield eq, len(f.precedences), 0

    dur2 = benchmark(f, (1,), n=1)
    Dispatcher.clear_all_cache()

    # Again check that cache is cleared.
    yield eq, len(f.methods), 0
    yield eq, len(f.precedences), 0

    dur3 = benchmark(f, (1,), n=1)

    # Check that caching yields improved timings.
    yield le, dur1, dur2 * 5
    yield le, dur2, dur1 * 5
    yield le, dur1, dur3 * 5
    yield le, dur3, dur1 * 5
