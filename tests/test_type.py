# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Union, PromisedType, as_type, TypeType, ResolutionError, Self
from . import le, raises, ok, nle


def test_corner_cases():
    yield raises, ResolutionError, lambda: PromisedType().resolve()
    yield raises, ResolutionError, lambda: Self().resolve()
    yield raises, RuntimeError, lambda: as_type({int, str}).mro()


def test_instance_check():
    t = Union(int, str)
    yield ok, isinstance(1, t)
    yield ok, isinstance('1', t)
    yield ok, not isinstance(1., t)


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
