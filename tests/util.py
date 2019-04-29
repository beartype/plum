# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from nose.tools import assert_raises, assert_equal, assert_less, \
    assert_less_equal, assert_not_equal, assert_greater, \
    assert_greater_equal, ok_
from time import time

le = assert_less_equal
lt = assert_less
eq = assert_equal
neq = assert_not_equal
ge = assert_greater_equal
gt = assert_greater
raises = assert_raises
ok = ok_


def benchmark(f, args, n=1000):
    """Benchmark the performance of a function `f` called with arguments
    `args` in microseconds.

    Args:
        f (function): Function to benchmark.
        args (tuple): Argument to call `f` with.
        n (int): Repetitions.
    """
    start = time()
    for i in range(n):
        f(*args)
    dur = time() - start
    return dur * 1e6 / n


def call(f, method, args, res):
    assert_equal(getattr(f, method)(*args), res)


def nle(x, y):
    assert (not (x <= y))


def assert_isinstance(x, y):
    assert isinstance(x, y)


def assert_issubclass(x, y):
    assert issubclass(x, y)


def isnotinstance(x, y):
    assert not isinstance(x, y)


def isnotsubclass(x, y):
    assert not issubclass(x, y)
