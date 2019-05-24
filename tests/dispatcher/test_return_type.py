# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import pytest

from plum import (
    Dispatcher,
    Referentiable,
    Self,
    Union,
    add_conversion_method
)
# noinspection PyUnresolvedReferences
from ..test_promotion import convert


def test_return_type():
    dispatch = Dispatcher()

    @dispatch({int, str}, return_type=int)
    def f(x):
        return x

    assert f(1) == 1
    assert f.invoke(int)(1) == 1
    with pytest.raises(TypeError):
        f('1')
    with pytest.raises(TypeError):
        f.invoke(str)('1')


def test_extension():
    dispatch = Dispatcher()

    @dispatch(int)
    def f(x):
        return x

    @f.extend(float, return_type=str)
    def f(x):
        return str(x)

    assert f(1.0) == '1.0'
    assert f.invoke(float)(1.0) == '1.0'


def test_multi():
    dispatch = Dispatcher()

    @dispatch.multi((int,), (str,), return_type=int)
    def g(x):
        return x

    assert g(1) == 1
    assert g.invoke(int)(1) == 1
    with pytest.raises(TypeError):
        g('1')
    with pytest.raises(TypeError):
        g.invoke(str)('1')


def test_inheritance():
    class A(object):
        def do(self, x):
            return 'hello from A'

    class B(A, Referentiable):
        _dispatch = Dispatcher(in_class=Self)

        @_dispatch(Union(int, Self, str), return_type=Union(int, Self))
        def do(self, x):
            return x

    b = B()

    assert b.do(1) == 1
    assert b.do(b) == b
    with pytest.raises(TypeError):
        b.do('1')
    assert b.do(1.0) == 'hello from A'


def test_conversion(convert):
    dispatch = Dispatcher()

    @dispatch({int, str}, return_type=int)
    def f(x):
        return x

    assert f(1) == 1
    with pytest.raises(TypeError):
        f('1')

    add_conversion_method(str, int, int)

    assert f(1) == 1
    assert f('1') == 1
