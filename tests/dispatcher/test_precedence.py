from typing import Union

import pytest

from plum import Dispatcher, AmbiguousLookupError

_dispatch = Dispatcher()


class Element:
    pass


class ZeroElement(Element):
    pass


class SpecialisedElement(Element):
    pass


@_dispatch
def mul(a: ZeroElement, b: Element):
    # Return zero.
    return a


@_dispatch
def mul(a: Element, b: SpecialisedElement):
    # Perform a specialised operation.
    return b


@_dispatch(precedence=1)
def mul_precedence(a: ZeroElement, b: Element):
    # Return zero.
    return a


@_dispatch
def mul_precedence(a: Element, b: SpecialisedElement):
    # Perform a specialised operation.
    return b


def test_precedence():
    zero = ZeroElement()
    el = Element()
    spel = SpecialisedElement()

    assert type(mul(zero, el)) == ZeroElement
    assert type(mul(el, spel)) == SpecialisedElement
    with pytest.raises(AmbiguousLookupError):
        mul(zero, spel)

    assert type(mul_precedence(zero, el)) == ZeroElement
    assert type(mul_precedence(el, spel)) == SpecialisedElement
    assert type(mul_precedence(zero, spel)) == ZeroElement


def test_extension():
    dispatch = Dispatcher()

    @dispatch
    def g(x):
        return "fallback"

    @g.dispatch(precedence=1)
    def g(x: Union[int, str]):
        return "int or str"

    @g.dispatch(precedence=2)
    def g(x: Union[int, float]):
        return "int or float"

    assert g("1") == "int or str"
    assert g(1.0) == "int or float"
    assert g(1) == "int or float"


def test_multi():
    dispatch = Dispatcher()

    @dispatch
    def g():
        return "fallback"

    @dispatch.multi((Union[int, str],), (Union[object, str],), precedence=1)
    def g(x):
        return "int or str, or object or str"

    @dispatch.multi((Union[int, float],), (float,), precedence=2)
    def g(x: Union[int, float]):
        return "int or float, or float"

    assert g("1") == "int or str, or object or str"
    assert g(1.0) == "int or float, or float"
    assert g(1) == "int or float, or float"
