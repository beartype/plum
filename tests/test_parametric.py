# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import eq, neq, ok
from . import parametric, type_parameter, Kind, kind


def test():
    class Base1: pass

    class Base2: pass

    @parametric
    class A(Base1, object): pass

    yield ok, issubclass(A, Base1)
    yield ok, not issubclass(A, Base2)

    yield ok, A(1) == A(1)
    yield ok, A(2) == A(2)
    yield ok, A(1) != A(2)

    a1 = A(1)()
    a2 = A(2)()

    yield ok, type(a1) == A(1)
    yield ok, type(a2) == A(2)
    yield ok, isinstance(a1, A(1))
    yield ok, not isinstance(a1, A(2))
    yield ok, issubclass(type(a1), A)
    yield ok, issubclass(type(a1), Base1)
    yield ok, not issubclass(type(a1), Base2)

    # Test multiple type parameters
    yield ok, A(1, 2) == A(1, 2)

    # Test type parameter extraction.
    yield eq, type_parameter(A(1)()), 1
    yield eq, type_parameter(A('1')()), '1'
    yield eq, type_parameter(A(1.)()), 1.
    yield eq, type_parameter(A(1, 2)()), (1, 2)
    yield eq, type_parameter(A(a1)()), id(a1)
    yield eq, type_parameter(A(a1, a2)()), (id(a1), id(a2))
    yield eq, type_parameter(A(1, a2)()), (1, id(a2))


def test_argument():
    @parametric
    class A(object):
        def __init__(self, x):
            self.x = x

    a = A(1)(5.)

    yield eq, a.x, 5.


def test_kind():
    yield eq, Kind(1), Kind(1)
    yield neq, Kind(1), Kind(2)
    yield eq, Kind(1)(1).get(), 1
    yield eq, Kind(2)(1, 2).get(), (1, 2)

    Kind2 = kind()
    yield neq, Kind2(1), Kind(1)
    yield eq, Kind(1), Kind(1)
    yield eq, Kind2(1), Kind2(1)
