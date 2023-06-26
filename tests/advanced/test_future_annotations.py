from __future__ import annotations

import math
from typing import Union

import pytest

from plum import Dispatcher, NotFoundLookupError

dispatch = Dispatcher()


class Number:
    def __init__(self, value):
        self.value = value

    @dispatch
    def __add__(self, other: Union[Number, int]) -> "Number":
        if isinstance(other, int):
            other_value = other
        else:
            other_value = other.value
        return Number(self.value + other_value)

    @staticmethod
    @dispatch
    def add_one(x: Number) -> Number:
        return x + 1

    @staticmethod
    @dispatch
    def add_one(x: str) -> Number:
        return Number.add_one(Number(float(x)))


def test_forward_reference():
    one = Number(1)
    two = Number(2)
    three = one + two
    assert isinstance(three, Number)
    assert three.value == 3

    three = one + 2
    assert isinstance(three, Number)
    assert three.value == 3

    with pytest.raises(NotFoundLookupError):
        three = one + 2.0


@pytest.mark.parametrize("one", [Number(1), "1"])
def test_staticmethod(one):
    two = Number.add_one(one)
    assert isinstance(two, Number)
    assert two.value == 2

    # Check that the docstring of :meth:`Number.add_one` still renders properly despite
    # the failed :meth:`Function._resolve_pending_registrations` when
    # :obj:`staticmethod` is instantiated. We simply check for the number of lines,
    # which suffices to see if both methods are included.
    assert len(Number.add_one.__doc__.splitlines()) == 3


def test_extension():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        return "int"

    assert f(1) == "int"
    with pytest.raises(NotFoundLookupError):
        f("1")

    def g(x: str):
        return "str"

    f.dispatch(g)

    assert f(1) == "int"
    assert f("1") == "str"

    # Extending `f` again will cause `g`s type hints to be processed again, which should
    # now be types rather than strings. We check that this also works.
    f.dispatch(g)

    assert f(1) == "int"
    assert f("1") == "str"


def test_extension_c():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        return x

    assert f(1) == 1
    with pytest.raises(NotFoundLookupError):
        f(4.0)

    f.dispatch(math.sqrt)

    assert f(1) == 1
    assert f(4.0) == 2
