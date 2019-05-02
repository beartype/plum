# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Union, PromisedType, as_type, TypeType, ResolutionError, Self, \
    VarArgs, Type, Referentiable, is_object, is_type
from . import ok, eq, neq, le, raises, nle, isnotinstance, isnotsubclass, \
    assert_issubclass, assert_isinstance


def test_varargs():
    yield eq, hash(VarArgs(int)), hash(VarArgs(int))
    yield eq, repr(VarArgs(int)), 'VarArgs({!r})'.format(Type(int))
    yield eq, VarArgs(int).expand(2), (Type(int), Type(int))
    yield ok, not VarArgs(int).parametric


def test_comparabletype():
    yield assert_isinstance, 1, Union(int)
    yield isnotinstance, '1', Union(int)
    yield assert_isinstance, '1', Union(int, str)
    yield assert_issubclass, Union(int), Union(int)
    yield assert_issubclass, Union(int), Union(int, str)
    yield isnotsubclass, Union(int, str), Union(int)
    yield eq, Union(int).mro(), int.mro()
    yield raises, RuntimeError, lambda: Union(int, str).mro()


def test_union():
    yield eq, hash(Union(int, str)), hash(Union(str, int))
    yield eq, repr(Union(int, str)), repr(Union(int, str))
    yield eq, set(Union(int, str).get_types()), {str, int}
    yield ok, not Union(int).parametric

    # Test equivalence between `Union` and `Type`.
    yield eq, hash(Union(int)), hash(Type(int))
    yield neq, hash(Union(int, str)), hash(Type(int))
    yield eq, repr(Union(int)), repr(Type(int))
    yield neq, repr(Union(int, str)), repr(Type(int))

    # Test lazy conversion to set.
    t = Union(int, int, str)
    yield assert_isinstance, t._types, tuple
    t.get_types()
    yield assert_isinstance, t._types, set

    # Test aliases.
    yield eq, repr(Union(int, alias='MyUnion')), 'tests.test_type.MyUnion'
    yield eq, repr(Union(int, str, alias='MyUnion')), 'tests.test_type.MyUnion'


def test_type():
    yield eq, hash(Type(int)), hash(Type(int))
    yield neq, hash(Type(int)), hash(Type(str))
    yield eq, repr(Type(int)), '{}.{}'.format(int.__module__, int.__name__)
    yield eq, Type(int).get_types(), (int,)
    yield ok, not Type(int).parametric


def test_promisedtype():
    t = PromisedType()
    yield raises, ResolutionError, lambda: hash(t)
    yield raises, ResolutionError, lambda: repr(t)
    yield raises, ResolutionError, lambda: t.get_types()

    t.deliver(Type(int))
    yield eq, hash(t), hash(Type(int))
    yield eq, repr(t), repr(Type(int))
    yield eq, t.get_types(), Type(int).get_types()
    yield ok, not t.parametric


class A(Referentiable):
    self = Self()


def test_self():
    yield eq, A.self, as_type(A)


def test_typetype():
    Promised = PromisedType()
    Promised.deliver(int)

    yield le, as_type(type(int)), TypeType
    yield le, as_type(type(Promised)), TypeType
    yield le, as_type(type({int})), TypeType
    yield le, as_type(type([int])), TypeType

    yield nle, as_type(int), TypeType
    yield nle, as_type(Promised), TypeType
    yield nle, as_type({int}), TypeType


def test_astype():
    # Need `ok` here: printing will resolve `Self`.
    yield ok, isinstance(as_type(Self), Self)
    yield assert_isinstance, as_type([]), VarArgs
    yield assert_isinstance, as_type([int]), VarArgs
    yield raises, TypeError, lambda: as_type([int, str])
    yield eq, as_type({int, str}), Union(int, str)
    yield eq, as_type(Type(int)), Type(int)
    yield eq, as_type(int), Type(int)
    yield raises, RuntimeError, lambda: as_type(1)


def test_is_object():
    yield ok, is_object(Type(object))
    yield ok, not is_object(Type(int))


def test_is_type():
    yield ok, is_type(int)
    yield ok, is_type({int})
    yield ok, is_type([int])
    yield ok, is_type(Type(int))
    yield ok, not is_type(1)
