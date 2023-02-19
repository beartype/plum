import pytest

from plum import AmbiguousLookupError, Dispatcher

dispatch = Dispatcher()


class Element:
    pass


class ZeroElement(Element):
    pass


class SpecialisedElement(Element):
    pass


@dispatch
def mul(a: ZeroElement, b: Element):
    # Return zero.
    return a


@dispatch
def mul(a: Element, b: SpecialisedElement):
    # Perform a specialised operation.
    return b


@dispatch(precedence=1)
def mul_precedence(a: ZeroElement, b: Element):
    # Return zero.
    return a


@dispatch
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
