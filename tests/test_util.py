import numpy as np

from plum.util import multihash, Comparable, is_in_class, get_class, get_context


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
