# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from plum.parametric import _types_of_iterable

from . import eq, neq, ok, isnotsubclass, assert_isinstance, isnotinstance, \
    assert_issubclass
from . import parametric, type_parameter, Kind, kind, Type, Union, type_of, \
    List, Tuple, as_type, PromisedType, Dispatcher, TypeType


def test():
    class Base1: pass

    class Base2: pass

    @parametric
    class A(Base1, object): pass

    yield assert_issubclass, A, Base1
    yield isnotsubclass, A, Base2

    yield ok, A(1) == A(1)
    yield ok, A(2) == A(2)
    yield ok, A(1) != A(2)

    a1 = A(1)()
    a2 = A(2)()

    yield eq, type(a1), A(1)
    yield eq, type(a2), A(2)
    yield assert_isinstance, a1, A(1)
    yield isnotinstance, a1, A(2)
    yield assert_issubclass, type(a1), A
    yield assert_issubclass, type(a1), Base1
    yield isnotsubclass, type(a1), Base2

    # Test multiple type parameters
    yield eq, A(1, 2), A(1, 2)

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

    # Test providing a superclass, where the default should be `object`.
    class SuperClass(object):
        pass

    Kind3 = kind(SuperClass)
    yield assert_issubclass, Kind3(1), SuperClass
    yield isnotsubclass, Kind2(1), SuperClass
    yield assert_issubclass, Kind2(1), object


def test_types_of_iterables():
    yield eq, _types_of_iterable([1]), Type(int)
    yield eq, _types_of_iterable(['1']), Type(str)
    yield eq, _types_of_iterable([1, '1']), Union(int, str)
    yield eq, _types_of_iterable((1,)), Type(int)
    yield eq, _types_of_iterable(('1',)), Type(str)
    yield eq, _types_of_iterable((1, '1')), Union(int, str)


def test_type_of():
    yield eq, type_of(1), Type(int)
    yield eq, type_of('1'), Type(str)
    yield eq, type_of([1]), List(int)
    yield eq, type_of([1, '1']), List({int, str})
    yield eq, type_of([1, '1', (1,)]), List({int, str, Tuple(int)})
    yield eq, type_of((1,)), Tuple(int)
    yield eq, type_of(('1',)), Tuple(str)
    yield eq, type_of((1, '1')), Tuple({int, str})
    yield eq, type_of((1, '1', [1])), Tuple({int, str, List(int)})


def test_listtype():
    # Standard type tests.
    yield eq, hash(List(int)), hash(List(int))
    yield neq, hash(List(int)), hash(List(str))
    yield eq, hash(List(List(int))), hash(List(List(int)))
    yield neq, hash(List(List(int))), hash(List(List(str)))
    yield eq, repr(List(int)), 'ListType({})'.format(repr(Type(int)))
    yield assert_issubclass, List(int).get_types()[0], list
    yield isnotsubclass, List(int).get_types()[0], int
    yield isnotsubclass, List(int).get_types()[0], tuple

    # Test instance check.
    yield assert_isinstance, [], List(Union())
    yield assert_isinstance, [1, 2], List(Union(int))

    # Check tracking of parametric.
    yield ok, List(int).parametric
    yield ok, as_type([List(int)]).parametric
    yield ok, as_type({List(int)}).parametric
    promise = PromisedType()
    promise.deliver(List(int))
    yield ok, promise.resolve().parametric

    # Test correctness.
    dispatch = Dispatcher()

    @dispatch(object)
    def f(x):
        return 'fallback'

    @dispatch(list)
    def f(x):
        return 'list'

    @dispatch(List(int))
    def f(x):
        return 'list of int'

    @dispatch(List(List(int)))
    def f(x):
        return 'list of list of int'

    yield eq, f([1]), 'list of int'
    yield eq, f(1), 'fallback'
    yield eq, f([1, 2]), 'list of int'
    yield eq, f([1, 2, '3']), 'list'
    yield eq, f([[1]]), 'list of list of int'
    yield eq, f([[1], [1]]), 'list of list of int'
    yield eq, f([[1], [1, 2]]), 'list of list of int'
    yield eq, f([[1], [1, 2, '3']]), 'list'


def test_tupletype():
    # Standard type tests.
    yield eq, hash(Tuple(int)), hash(Tuple(int))
    yield neq, hash(Tuple(int)), hash(Tuple(str))
    yield eq, hash(Tuple(Tuple(int))), hash(Tuple(Tuple(int)))
    yield neq, hash(Tuple(Tuple(int))), hash(Tuple(Tuple(str)))
    yield eq, repr(Tuple(int)), 'TupleType({})'.format(repr(Type(int)))
    yield assert_issubclass, Tuple(int).get_types()[0], tuple
    yield isnotsubclass, Tuple(int).get_types()[0], int
    yield isnotsubclass, Tuple(int).get_types()[0], list

    # Test instance check.
    yield assert_isinstance, (), Tuple(Union())
    yield assert_isinstance, (1, 2), Tuple(Union(int))

    # Check tracking of parametric.
    yield ok, Tuple(int).parametric
    yield ok, as_type([Tuple(int)]).parametric
    yield ok, as_type({Tuple(int)}).parametric
    promise = PromisedType()
    promise.deliver(Tuple(int))
    yield ok, promise.resolve().parametric

    # Test correctness.
    dispatch = Dispatcher()

    @dispatch(object)
    def f(x):
        return 'fallback'

    @dispatch(tuple)
    def f(x):
        return 'tup'

    @dispatch(Tuple(int))
    def f(x):
        return 'tup of int'

    @dispatch(Tuple(Tuple(int)))
    def f(x):
        return 'tup of tup of int'

    yield eq, f((1,)), 'tup of int'
    yield eq, f(1), 'fallback'
    yield eq, f((1, 2)), 'tup of int'
    yield eq, f((1, 2, '3')), 'tup'
    yield eq, f(((1,),)), 'tup of tup of int'
    yield eq, f(((1,), (1,))), 'tup of tup of int'
    yield eq, f(((1,), (1, 2))), 'tup of tup of int'
    yield eq, f(((1,), (1, 2, '3'))), 'tup'


def test_covariance():
    yield assert_issubclass, List(int), List(object)
    yield assert_issubclass, List(List(int)), List(List(object))
    yield isnotsubclass, List(int), List(str)
    yield isnotsubclass, List(List), List(int)
    yield assert_issubclass, List(List), List(TypeType)
