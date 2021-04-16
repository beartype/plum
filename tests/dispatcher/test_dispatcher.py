import pytest
from typing import Union, List

from plum import Dispatcher, NotFoundLookupError


def test_keywords():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int, option=None):
        return x

    assert f(2) == 2
    assert f(2, option=None) == 2
    with pytest.raises(NotFoundLookupError):
        f(2, None)


def test_redefinition():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        return "first"

    assert f(1) == "first"

    @dispatch
    def f(x: int):
        return "second"

    assert f(1) == "second"


def test_metadata_and_printing():
    dispatch = Dispatcher()

    class A:
        _dispatch = Dispatcher()

        @_dispatch
        def g(self):
            """docstring of g"""

    @dispatch
    def f():
        """docstring of f"""

    assert f.__name__ == "f"
    assert f.__doc__ == "docstring of f"
    assert f.__module__ == "tests.dispatcher.test_dispatcher"
    assert repr(f) == f"<function {f._f} with 1 method(s)>"

    assert f.invoke().__name__ == "f"
    assert f.invoke().__doc__ == "docstring of f"
    assert f.invoke().__module__ == "tests.dispatcher.test_dispatcher"
    n = len(hex(id(f))) + 1  # Do not check memory address and extra ">".
    assert repr(f.invoke())[:-n] == repr(f._f)[:-n]

    a = A()
    g = a.g

    assert g.__name__ == "g"
    assert g.__doc__ == "docstring of g"
    assert g.__module__ == "tests.dispatcher.test_dispatcher"
    assert repr(g) == f'<function {A._dispatch._classes[A]["g"]._f} with 1 method(s)>'

    assert g.invoke().__name__ == "g"
    assert g.invoke().__doc__ == "docstring of g"
    assert g.invoke().__module__ == "tests.dispatcher.test_dispatcher"
    assert repr(g.invoke())[:-n] == repr(A._dispatch._classes[A]["g"]._f)[:-n]


def test_multi():
    dispatch = Dispatcher()

    @dispatch
    def f(x):
        return "fallback"

    @dispatch.multi((int,), (str,))
    def f(x: Union[int, str]):
        return "int or str"

    assert f(1) == "int or str"
    assert f("1") == "int or str"
    assert f(1.0) == "fallback"


def test_multi_in_class():
    dispatch = Dispatcher()

    class A:
        @dispatch
        def f(self, x):
            return "fallback"

        @dispatch.multi(
            (
                object,
                int,
            ),
            (
                object,
                str,
            ),
        )
        def f(self, x: Union[int, str]):
            return "int or str"

    a = A()
    assert a.f(1) == "int or str"
    assert a.f("1") == "int or str"
    assert a.f(1.0) == "fallback"


def test_extension():
    dispatch = Dispatcher()

    @dispatch
    def f():
        return "fallback"

    @f.dispatch
    def f(x: int):
        return "int"

    @f.dispatch_multi((str,), (float,))
    def f(x: Union[str, float]):
        return "str or float"

    assert f() == "fallback"
    assert f(1) == "int"
    assert f("1") == "str or float"
    assert f(1.0) == "str or float"


def test_invoke():
    dispatch = Dispatcher()

    @dispatch()
    def f():
        return "fallback"

    @dispatch
    def f(x: int):
        return "int"

    @dispatch
    def f(x: str):
        return "str"

    @dispatch
    def f(x: Union[int, str, float]):
        return "int, str, or float"

    assert f() == "fallback"
    assert f(1) == "int"
    assert f("1") == "str"
    assert f(1.0) == "int, str, or float"
    assert f.invoke()() == "fallback"
    assert f.invoke(int)("1") == "int"
    assert f.invoke(str)(1) == "str"
    assert f.invoke(float)(1) == "int, str, or float"
    assert f.invoke(Union[int, str])(1) == "int, str, or float"
    assert f.invoke(Union[int, str, float])(1) == "int, str, or float"


def test_invoke_in_class():
    dispatch = Dispatcher()

    class A:
        def do(self, x):
            return "fallback"

    class B(A):
        @dispatch
        def do(self, x: int):
            return "int"

    class C(B):
        @dispatch
        def do(self, x: str):
            return "str"

    c = C()

    # Test bound calls.
    assert c.do.invoke(str)("1") == "str"
    assert c.do.invoke(int)(1) == "int"
    assert c.do.invoke(float)(1.0) == "fallback"

    # Test unbound calls.
    assert C.do.invoke(C, str)(c, "1") == "str"
    assert C.do.invoke(C, int)(c, 1) == "int"
    assert C.do.invoke(C, float)(c, 1.0) == "fallback"


def test_parametric_tracking():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        pass

    assert not f._parametric
    f(1)
    assert not f._parametric

    @dispatch
    def f(x: List[int]):
        pass

    assert not f._parametric
    f(1)
    assert f._parametric
