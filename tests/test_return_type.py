# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import dispatch, Dispatcher, Referentiable, Self, Union
from . import eq, raises


def test_return_type():
    @dispatch({int, str}, return_type=int)
    def f(x):
        return x

    yield eq, f(1), 1
    yield raises, TypeError, lambda: f('1')

    # Test extension.
    @f.extend(float, return_type=str)
    def f(x):
        return str(x)

    yield eq, f(1.0), '1.0'

    # Test multiple signatures.
    @dispatch.multi((int,), (str,), return_type=int)
    def g(x):
        return x

    yield eq, g(1), 1
    yield raises, TypeError, lambda: g('1')

    # Test that invocation gets around it.
    yield eq, g.invoke(str)('1'), '1'


class A(object):
    def do(self, x):
        return 'hello from A'


class B(A, Referentiable):
    dispatch = Dispatcher(in_class=Self)

    @dispatch(Union(int, Self, str), return_type={int, Self})
    def do(self, x):
        return x


def test_inheritance():
    b = B()

    yield eq, b.do(1), 1
    yield eq, b.do(b), b
    yield raises, TypeError, lambda: b.do('1')
    yield eq, b.do(1.0), 'hello from A'
