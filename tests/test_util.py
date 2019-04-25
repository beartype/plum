# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from plum.util import multihash, Comparable, get_default
import numpy as np

from . import ok, eq, neq, le, lt, ge, gt


def test_multihash():
    yield eq, multihash(1, 2), multihash(1, 2)
    yield neq, multihash(2, 2), multihash(1, 2)
    yield neq, multihash(2, 1), multihash(1, 2)


class Number(Comparable):
    def __init__(self, x):
        self.x = x

    def __le__(self, other):
        return self.x <= other.x


def test_comparable():
    yield eq, Number(1), Number(1)
    yield neq, Number(1), Number(2)
    yield le, Number(1), Number(2)
    yield le, Number(1), Number(1)
    yield lt, Number(1), Number(2)
    yield ge, Number(2), Number(1)
    yield ge, Number(2), Number(2)
    yield gt, Number(2), Number(1)
    yield ok, Number(1).is_comparable(Number(2))
    yield ok, not Number(1).is_comparable(Number(np.nan))


def test_get_default():
    d = {'key': 'value'}

    yield eq, get_default(d, 'key', 1), 'value'
    yield eq, get_default(d, 'key2', 1), 1
