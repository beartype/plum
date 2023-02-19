from typing import Union

import pytest

from plum import Dispatcher, add_conversion_method


def test_return_type():
    dispatch = Dispatcher()

    @dispatch
    def f(x: Union[int, str]) -> int:
        return x

    assert f(1) == 1
    assert f.invoke(int)(1) == 1
    with pytest.raises(TypeError):
        f("1")
    with pytest.raises(TypeError):
        f.invoke(str)("1")


class A:
    def do(self, x):
        return "hello from A"


dispatch = Dispatcher()


class B(A):
    @dispatch
    def do(self, x: Union[int, "B", str]) -> Union[int, "B"]:
        return x


def test_inheritance():
    b = B()

    assert b.do(1) == 1
    assert b.do(b) == b
    with pytest.raises(TypeError):
        b.do("1")
    assert b.do(1.0) == "hello from A"


dispatch = Dispatcher()


class A2:
    @dispatch
    def do(self, x: "A2", ok=True) -> "A2":
        if ok:
            return x
        else:
            return 2


def test_inheritance_self_return():
    a = A2()
    assert a.do(a) is a
    with pytest.raises(TypeError):
        a.do(a, ok=False)


def test_conversion(convert):
    dispatch = Dispatcher()

    @dispatch
    def f(x: Union[int, str]) -> int:
        return x

    assert f(1) == 1
    with pytest.raises(TypeError):
        f("1")

    add_conversion_method(str, int, int)

    assert f(1) == 1
    assert f("1") == 1
