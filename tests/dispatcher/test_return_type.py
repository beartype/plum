import pytest
from typing import Union

from plum import Dispatcher, add_conversion_method

# noinspection PyUnresolvedReferences
from ..test_promotion import convert


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


def test_extension():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        return x

    @f.dispatch
    def f(x: float) -> str:
        return str(x)

    assert f(1.0) == "1.0"
    assert f.invoke(float)(1.0) == "1.0"


def test_multi():
    dispatch = Dispatcher()

    @dispatch.multi((int,), (str,), return_type=int)
    def g(x: Union[int, str]) -> int:
        return x

    assert g(1) == 1
    assert g.invoke(int)(1) == 1
    with pytest.raises(TypeError):
        g("1")
    with pytest.raises(TypeError):
        g.invoke(str)("1")


def test_inheritance():
    class A:
        def do(self, x):
            return "hello from A"

    class B(A):
        _dispatch = Dispatcher()

        @_dispatch
        def do(self, x: Union[int, "B", str]) -> Union[int, "B"]:
            return x

    b = B()

    assert b.do(1) == 1
    assert b.do(b) == b
    with pytest.raises(TypeError):
        b.do("1")
    assert b.do(1.0) == "hello from A"


def test_inheritance_self_return():
    class A:
        _dispatch = Dispatcher()

        @_dispatch
        def do(self, x: "A", ok=True) -> "A":
            if ok:
                return x
            else:
                return 2

    a = A()
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
