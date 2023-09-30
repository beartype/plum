import sys
import typing

import numpy as np
import pytest

from plum.repr import repr_short
from plum.util import (
    Comparable,
    Missing,
    get_class,
    get_context,
    is_in_class,
    multihash,
    wrap_lambda,
)


def test_repr_short():
    class A:
        pass

    assert repr_short(int) == "int"
    assert repr_short(A) == "tests.test_util.test_repr_short.<locals>.A"
    assert repr_short(typing.Union[int, float]) == "typing.Union[int, float]"


def test_missing():
    # `Missing` cannot be instantiated.
    with pytest.raises(TypeError):
        Missing()

    # `Missing` also has no boolean value.
    with pytest.raises(TypeError):
        bool(Missing)

    # However, if Sphinx is loaded, `Missing` should evaluate to `False`.
    assert "sphinx" not in sys.modules
    sys.modules["sphinx"] = None
    assert not Missing
    del sys.modules["sphinx"]


def test_multihash():
    assert multihash(1, 2) == multihash(1, 2)
    assert multihash(2, 2) != multihash(1, 2)
    assert multihash(2, 1) != multihash(1, 2)


class Number(Comparable):
    def __init__(self, x):
        self.x = x

    def __le__(self, other):
        return self.x <= other.x


def test_comparable():
    assert Number(1) == Number(1)
    assert Number(1) != Number(2)
    assert Number(1) <= Number(2)
    assert Number(1) <= Number(1)
    assert Number(1) < Number(2)
    assert Number(2) >= Number(1)
    assert Number(2) >= Number(2)
    assert Number(2) > Number(1)
    assert Number(1).is_comparable(Number(2))
    assert not Number(1).is_comparable(Number(np.nan))


class A:
    def f(self):
        pass


def f(self):
    pass


def test_wrap_lambda():
    assert wrap_lambda(int)("1") == 1


def test_is_in_class():
    assert is_in_class(A.f)
    assert is_in_class(A().f)
    assert not is_in_class(f)
    assert not is_in_class(lambda _: None)


def test_get_class():
    assert get_class(A.f) == "tests.test_util.A"
    assert get_class(A().f) == "tests.test_util.A"


def test_get_context():
    assert get_context(A.f) == "tests.test_util"
    assert get_context(A().f) == "tests.test_util"
    assert get_context(f) == "tests.test_util"
    assert get_context(lambda _: None) == "tests.test_util.test_get_context.<locals>"
