# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import dispatch, AmbiguousLookupError
from . import eq, raises


class Element(object):
    pass


class ZeroElement(Element):
    pass


class SpecialisedElement(Element):
    pass


@dispatch(ZeroElement, Element)
def mul(a, b):
    # Return zero.
    return a


@dispatch(Element, SpecialisedElement)
def mul(a, b):
    # Perform a specialised operation.
    return b


@dispatch(ZeroElement, Element, precedence=1)
def mul_precedence(a, b):
    # Return zero.
    return a


@dispatch(Element, SpecialisedElement)
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
