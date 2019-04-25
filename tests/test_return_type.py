# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Dispatcher, Referentiable, Self, Union, convert, \
    add_conversion_method
from . import eq, raises
from .test_promotion import save_convert_methods, restore_convert_methods


def test_return_type():
    dispatch = Dispatcher()

    @dispatch({int, str}, return_type=int)
    def f(x):
        return x

    yield eq, f(1), 1
    yield eq, f.invoke(int)(1), 1
    yield raises, TypeError, lambda: f('1')
    yield raises, TypeError, lambda: f.invoke(str)('1')


def test_extension():
    dispatch = Dispatcher()

    @dispatch(int)
    def f(x):
        return x

    @f.extend(float, return_type=str)
    def f(x):
        return str(x)

    yield eq, f(1.0), '1.0'
    yield eq, f.invoke(float)(1.0), '1.0'


def test_multi():
    dispatch = Dispatcher()

    @dispatch.multi((int,), (str,), return_type=int)
    def g(x):
        return x

    yield eq, g(1), 1
    yield eq, g.invoke(int)(1), 1
    yield raises, TypeError, lambda: g('1')
    yield raises, TypeError, lambda: g.invoke(str)('1')


class A(object):
    def do(self, x):
        return 'hello from A'


class B(A, Referentiable):
    dispatch = Dispatcher(in_class=Self)

    @dispatch(Union(int, Self, str), return_type=Union(int, Self))
    def do(self, x):
        return x


def test_inheritance():
    b = B()

    yield eq, b.do(1), 1
    yield eq, b.do(b), b
    yield raises, TypeError, lambda: b.do('1')
    yield eq, b.do(1.0), 'hello from A'


def test_conversion():
    dispatch = Dispatcher()

    convert_methods = save_convert_methods()

    @dispatch({int, str}, return_type=int)
    def f(x):
        return x

    yield eq, f(1), 1
    yield raises, TypeError, lambda: f('1')

    add_conversion_method(str, int, int)

    yield eq, f(1), 1
    yield eq, f('1'), 1

    restore_convert_methods(convert_methods)
