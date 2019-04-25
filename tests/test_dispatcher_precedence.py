# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Dispatcher, AmbiguousLookupError
from . import eq, raises

_dispatch = Dispatcher()


class Element(object):
    pass


class ZeroElement(Element):
    pass


class SpecialisedElement(Element):
    pass


@_dispatch(ZeroElement, Element)
def mul(a, b):
    # Return zero.
    return a


@_dispatch(Element, SpecialisedElement)
def mul(a, b):
    # Perform a specialised operation.
    return b


@_dispatch(ZeroElement, Element, precedence=1)
def mul_precedence(a, b):
    # Return zero.
    return a


@_dispatch(Element, SpecialisedElement)
def mul_precedence(a, b):
    # Perform a specialised operation.
    return b


def test_precedence():
    zero = ZeroElement()
    el = Element()
    spel = SpecialisedElement()

    yield eq, type(mul(zero, el)), ZeroElement
    yield eq, type(mul(el, spel)), SpecialisedElement
    yield raises, AmbiguousLookupError, lambda: mul(zero, spel)

    yield eq, type(mul_precedence(zero, el)), ZeroElement
    yield eq, type(mul_precedence(el, spel)), SpecialisedElement
    yield eq, type(mul_precedence(zero, spel)), ZeroElement


def test_extension():
    dispatch = Dispatcher()

    @dispatch()
    def g(x):
        return 'fallback'

    @g.extend({int, str}, precedence=1)
    def g(x):
        return 'int or str'

    @g.extend({int, float}, precedence=2)
    def g(x):
        return 'int or float'

    yield eq, g('1'), 'int or str'
    yield eq, g(1.0), 'int or float'
    yield eq, g(1), 'int or float'


def test_multi():
    dispatch = Dispatcher()

    @dispatch()
    def g():
        return 'fallback'

    @dispatch.multi(({int, str},), ({object, str},), precedence=1)
    def g(x):
        return 'int or str, or object or str'

    @dispatch.multi(({int, float},), (float,), precedence=2)
    def g(x):
        return 'int or float, or float'

    yield eq, g('1'), 'int or str, or object or str'
    yield eq, g(1.0), 'int or float, or float'
    yield eq, g(1), 'int or float, or float'
