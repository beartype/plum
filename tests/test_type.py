# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import pytest

from plum import (
    Union,
    PromisedType,
    as_type,
    TypeType,
    ResolutionError,
    Self,
    VarArgs,
    Type,
    Referentiable,
    is_object,
    is_type,
    Callable
)


def test_varargs():
    assert hash(VarArgs(int)) == hash(VarArgs(int))
    assert repr(VarArgs(int)) == 'VarArgs({!r})'.format(Type(int))
    assert VarArgs(int).expand(2) == (Type(int), Type(int))
    assert not VarArgs(int).parametric


def test_comparabletype():
    assert isinstance(1, Union(int))
    assert not isinstance('1', Union(int))
    assert isinstance('1', Union(int, str))
    assert issubclass(Union(int), Union(int))
    assert issubclass(Union(int), Union(int, str))
    assert not issubclass(Union(int, str), Union(int))
    assert Union(int).mro() == int.mro()
    with pytest.raises(RuntimeError):
        Union(int, str).mro()


def test_union():
    assert hash(Union(int, str)) == hash(Union(str, int))
    assert repr(Union(int, str)) == repr(Union(int, str))
    assert set(Union(int, str).get_types()) == {str, int}
    assert not Union(int).parametric

    # Test equivalence between `Union` and `Type`.
    assert hash(Union(int)) == hash(Type(int))
    assert hash(Union(int, str)) != hash(Type(int))
    assert repr(Union(int)) == repr(Type(int))
    assert repr(Union(int, str)) != repr(Type(int))

    # Test lazy conversion to set.
    t = Union(int, int, str)
    assert isinstance(t._types, tuple)
    t.get_types()
    assert isinstance(t._types, set)

    # Test aliases.
    assert repr(Union(int, alias='MyUnion')) == 'tests.test_type.MyUnion'
    assert repr(Union(int, str, alias='MyUnion')) == 'tests.test_type.MyUnion'


def test_type():
    assert hash(Type(int)) == hash(Type(int))
    assert hash(Type(int)) != hash(Type(str))
    assert repr(Type(int)) == '{}.{}'.format(int.__module__, int.__name__)
    assert Type(int).get_types() == (int,)
    assert not Type(int).parametric


def test_promisedtype():
    t = PromisedType()
    with pytest.raises(ResolutionError):
        hash(t)
    with pytest.raises(ResolutionError):
        repr(t)
    with pytest.raises(ResolutionError):
        t.get_types()

    t.deliver(Type(int))
    assert hash(t) == hash(Type(int))
    assert repr(t) == repr(Type(int))
    assert t.get_types() == Type(int).get_types()
    assert not t.parametric


class A(Referentiable):
    self = Self()


def test_self():
    assert A.self == as_type(A)


def test_typetype():
    Promised = PromisedType()
    Promised.deliver(int)

    assert as_type(type(int)) <= TypeType
    assert as_type(type(Promised)) <= TypeType
    assert as_type(type({int})) <= TypeType
    assert as_type(type([int])) <= TypeType

    assert not (as_type(int) <= TypeType)
    assert not (as_type(Promised) <= TypeType)
    assert not (as_type({int}) <= TypeType)


def test_astype():
    # Need `ok` here: printing will resolve `Self`.
    assert isinstance(as_type(Self), Self)
    assert isinstance(as_type([]), VarArgs)
    assert isinstance(as_type([int]), VarArgs)
    with pytest.raises(TypeError):
        as_type([int, str])
    assert as_type({int, str}) == Union(int, str)
    assert as_type(Type(int)) == Type(int)
    assert as_type(int) == Type(int)
    with pytest.raises(RuntimeError):
        as_type(1)


def test_is_object():
    assert is_object(Type(object))
    assert not is_object(Type(int))


def test_is_type():
    assert is_type(int)
    assert is_type({int})
    assert is_type([int])
    assert is_type(Type(int))
    assert not is_type(1)


def test_callable():
    class A(object):
        pass

    class B(object):
        def __call__(self):
            pass

    # Check `__instancecheck__`.
    assert not isinstance(1, Callable)
    assert isinstance(lambda x: x, Callable)
    assert not isinstance(A(), Callable)
    assert isinstance(B(), Callable)

    # Check `__subclasscheck__`.
    assert not issubclass(int, Callable)
    assert issubclass(type(lambda x: x), Callable)
    assert not issubclass(A, Callable)
    assert issubclass(B, Callable)
    assert issubclass(Callable, Callable)
