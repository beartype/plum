# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Union, PromisedType, as_type, TypeType, ResolutionError, Self, \
    VarArgs, Type, Referentiable
from . import eq, neq, le, raises, nle, isnotinstance, isnotsubclass


def test_varargs():
    yield eq, hash(VarArgs(int)), hash(VarArgs(int))
    yield eq, repr(VarArgs(int)), 'VarArgs({!r})'.format(Type(int))
    yield eq, VarArgs(int).expand(2), (Type(int), Type(int))


def test_comparabletype():
    yield isinstance, 1, Union(int)
    yield isnotinstance, '1', Union(int)
    yield isinstance, '1', Union(int, str)
    yield issubclass, Union(int), Union(int)
    yield issubclass, Union(int), Union(int, str)
    yield isnotsubclass, Union(int, str), Union(int)
    yield eq, Union(int).mro(), int.mro()
    yield raises, RuntimeError, lambda: Union(int, str).mro()


def test_union():
    yield eq, hash(Union(int, str)), hash(Union(str, int))
    yield eq, \
          repr(Union(int, str)), \
          '{{{!r}, {!r}}}'.format(Type(int), Type(str))
    yield eq, set(Union(int, str).get_types()), {str, int}


def test_type():
    yield eq, hash(Type(int)), hash(Type(int))
    yield neq, hash(Type(int)), hash(Type(str))
    yield eq, repr(Type(int)), '{}.{}'.format(int.__module__, int.__name__)
    yield eq, Type(int).get_types(), (int,)


def test_promisedtype():
    t = PromisedType()
    yield raises, ResolutionError, lambda: hash(t)
    yield raises, ResolutionError, lambda: repr(t)
    yield raises, ResolutionError, lambda: t.get_types()

    t.deliver(Type(int))
    yield eq, hash(t), hash(Type(int))
    yield eq, repr(t), repr(Type(int))
    yield eq, t.get_types(), Type(int).get_types()


def test_self():
    class A(Referentiable):
        self = Self()

    yield eq, A.self, as_type(A)


def test_typetype():
    Promised = PromisedType()
    Promised.deliver(int)

    yield le, as_type(type(int)), as_type(TypeType)
    yield le, as_type(type(Promised)), as_type(TypeType)
    yield le, as_type(type({int})), as_type(TypeType)
    yield le, as_type(type([int])), as_type(TypeType)

    yield nle, as_type(int), as_type(TypeType)
    yield nle, as_type(Promised), as_type(TypeType)
    yield nle, as_type({int}), as_type(TypeType)


def test_astype():
    yield isinstance, as_type(Self), Self
    yield isinstance, as_type([]), VarArgs
    yield isinstance, as_type([int]), VarArgs
    yield raises, TypeError, lambda: as_type([int, str])
    yield eq, as_type({int, str}), Union(int, str)
    yield eq, as_type(Type(int)), Type(int)
    yield eq, as_type(int), Type(int)
    yield raises, RuntimeError, lambda: as_type(1)
