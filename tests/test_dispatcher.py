import pytest

from plum import Dispatcher
from plum.signature import Signature as Sig


def test_dispatch_function():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        pass

    @dispatch(precedence=1)
    def g(x: float):
        pass

    assert set(dispatch.functions.keys()) == {"f", "g"}
    assert dispatch.functions["f"].methods[0].signature == Sig(int)
    assert dispatch.functions["g"].methods[0].signature == Sig(float, precedence=1)


def test_dispatch_class():
    dispatch = Dispatcher()

    class A:
        @dispatch
        def f(x: int):
            pass

    class B:
        @dispatch(precedence=1)
        def g(x: float):
            pass

    a = "tests.test_dispatcher.test_dispatch_class.<locals>.A"
    b = "tests.test_dispatcher.test_dispatch_class.<locals>.B"
    assert set(dispatch.classes.keys()) == {a, b}
    assert dispatch.classes[a]["f"].methods[0].signature == Sig(int)
    assert dispatch.classes[b]["g"].methods[0].signature == Sig(float, precedence=1)


def test_dispatch_multi():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        return "int"

    @dispatch.multi((float,), Sig(str, precedence=1))
    def f(x):
        return "float or str"

    assert f(1) == "int"
    assert f(1.0) == "float or str"
    assert f("1") == "float or str"
    assert dispatch.functions["f"].methods[2].signature.precedence == 1

    # Check that arguments to `dispatch.multi` must be tuples or signatures.
    with pytest.raises(ValueError):
        dispatch.multi(1)


def test_abstract():
    dispatch = Dispatcher()

    @dispatch.abstract
    def f(x):
        """Docs"""

    assert f.__doc__ == "Docs"
    assert f.methods == []
