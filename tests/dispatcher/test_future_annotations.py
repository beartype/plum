from __future__ import annotations

from typing import Union
import math

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
