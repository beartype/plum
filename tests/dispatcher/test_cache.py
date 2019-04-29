# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Dispatcher, ListType
from . import eq, le, benchmark


def test_cache():
    # Test performance.
    dispatch = Dispatcher()

    def f_native(x): return None

    @dispatch(object)
    def f(x):
        return 1

    @dispatch({int, float})
    def f(x):
        return 1

    @dispatch({int, float, str})
    def f(x):
        return 1

    dur_native = benchmark(f_native, (1,))
    dur_plum_first = benchmark(f, (1,), n=1)
    dur_plum = benchmark(f, (1,))

    # A cached call should not be more than 500 times slower than a native call.
    yield le, dur_plum, 500 * dur_native, 'compare native'

    # A first call should not be more than 100 times slower than a cached call.
    yield le, dur_plum_first, 100 * dur_plum, 'compare first'

    # The cached call should be at least 10 times faster than a first call.
    yield le, dur_plum, dur_plum_first / 10, 'cache performance'

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

    @dispatch(ListType(int))
    def f(x):
        return 1

    f(1)

    # Check that cache is used.
    yield eq, len(f.methods), 2
    yield eq, len(f.precedences), 2
    yield eq, f._parametric, True

    dispatch.clear_cache()

    # Check that cache is cleared.
    yield eq, len(f.methods), 0
    yield eq, len(f.precedences), 0
    yield eq, f._parametric, False

    f(1)
    Dispatcher.clear_all_cache()

    # Again check that cache is cleared.
    yield eq, len(f.methods), 0
    yield eq, len(f.precedences), 0
    yield eq, f._parametric, False
