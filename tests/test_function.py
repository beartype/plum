import abc
import typing

import pytest

from plum import Dispatcher
from plum.function import Function, _change_function_name, _convert
from plum.resolver import AmbiguousLookupError, NotFoundLookupError, Resolver
from plum.signature import Signature


def test_convert_reference():
    class A:
        pass

    a = A()
    assert _convert(a, typing.Any) is a  # Nothing should happen.
    assert _convert(a, tuple) == (a,)


def test_change_function_name():
    def f(x):
        """Doc"""

    g = _change_function_name(f, "g")

    assert g.__name__ == "g"
    assert g.__doc__ == "Doc"


def test_function():
    def f(x):
        """Doc"""

    g = Function(f)

    assert g.__name__ == "f"
    assert g.__doc__ == "Doc"

    # Check global tracking of functions.
    assert Function._instances[-1] == g


def test_repr():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        return "int"

    @dispatch
    def f(x: str):
        return "str"

    assert repr(f) == f"<function {f._f} with 0 registered and 2 pending method(s)>"

    # Register all methods.
    assert f(1) == "int"

    assert repr(f) == f"<function {f._f} with 2 registered and 0 pending method(s)>"

    @dispatch
    def f(x: float):
        return "float"

    assert repr(f) == f"<function {f._f} with 2 registered and 1 pending method(s)>"

    # Again register all methods.
    assert f(1) == "int"

    assert repr(f) == f"<function {f._f} with 3 registered and 0 pending method(s)>"


# `A` needs to be in the global scope for owner resolution to work.


class A:
    pass


def test_owner():
    def f(x):
        """Doc"""

    assert Function(f).owner is None
    assert Function(f, owner="A").owner is A


def test_doc(monkeypatch):
    # Test empty documentation.
    assert Function(lambda: None).__doc__ is None

    # Test the self-exclusion mechanism.
    def f(x: int):
        """Doc"""

    f = Function(f).dispatch(f)
    assert f.__doc__ == "Doc"

    @f.dispatch
    def f(x: float):
        pass

    assert "further implementations" in f.__doc__

    # Let the resolver return something simple to make testing easier.
    monkeypatch.setattr(Resolver, "doc", lambda _, exclude: "more docs")

    def f(x: int):
        """Doc"""

    f = Function(f).dispatch(f)
    assert f.__doc__ == (
        "Doc\n\n"
        "This function has further implementations documented below.\n\n"
        "more docs"
    )


def test_methods():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        pass

    @dispatch
    def f(x: float):
        pass

    assert f.methods == [Signature(int), Signature(float)]


def test_function_dispatch():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        return "int"

    @f.dispatch
    def implementation(x: float):
        return "float"

    @f.dispatch(precedence=1)
    def other_implementation(x: str):
        return "str"

    assert f(1) == "int"
    assert f(1.0) == "float"
    assert f("1") == "str"
    assert f._resolver.resolve(("1",)).precedence == 1


def test_function_multi_dispatch():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        return "int"

    @f.dispatch_multi((float,), Signature(str, precedence=1))
    def implementation(x):
        return "float or str"

    assert f(1) == "int"
    assert f(1.0) == "float or str"
    assert f("1") == "float or str"
    assert f._resolver.resolve(("1",)).precedence == 1

    # Check that arguments to `f.dispatch_multi` must be tuples or signatures.
    with pytest.raises(ValueError):
        f.dispatch_multi(1)


def test_register():
    def f(x: int):
        pass

    g = Function(f)
    g.register(f)

    assert g._pending == [(f, None, 0)]
    assert g._resolved == []
    assert len(g._resolver) == 0


def test_resolve_pending_registrations():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        return "int"

    # Populate cache.
    assert f(1) == "int"

    # At this point, there should be nothing to register, so a call should not clear
    # the cache.
    assert f._pending == []
    f._resolve_pending_registrations()
    assert len(f._cache) == 1

    @f.dispatch
    def f(x: str):
        pass

    # Now there is something to register. A call should clear the cache.
    assert len(f._pending) == 1
    f._resolve_pending_registrations()
    assert len(f._pending) == 0
    assert len(f._cache) == 0

    # Register in two ways using multi and the wrong name.
    @f.dispatch_multi((float,), Signature(complex))
    def not_f(x):
        return "float or complex"

    # Even though we used `not_f`, dispatch should work correctly.
    assert not_f(1.0) == "float or complex"
    assert not_f(1j) == "float or complex"

    # Check the expansion of default values.

    @dispatch
    def g(x: int, y: float = 1.0, z: complex = 1j):
        return "ok"

    assert g(1) == "ok"
    assert g(1, 1.0) == "ok"
    assert g(1, 1.0, 1j) == "ok"

    assert g(1, y=1.0, z=1j) == "ok"
    assert g(1, 1.0, z=1j) == "ok"


def test_enhance_exception():
    def f():
        pass

    f = Function(f).dispatch(f)

    def g():
        pass

    g = Function(g, owner="A").dispatch(g)

    e = ValueError("Go!")

    assert isinstance(f._enhance_exception(e), ValueError)
    assert str(f._enhance_exception(e)) == "For function `f`, go!"

    assert isinstance(g._enhance_exception(e), ValueError)
    assert (
        str(g._enhance_exception(e))
        == "For function `g` of `tests.test_function.A`, go!"
    )


def test_call_exception_enhancement():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int, y):
        pass

    @dispatch
    def f(x, y: int):
        pass

    with pytest.raises(NotFoundLookupError, match="(?i)^for function `f`, "):
        f("1", "1")

    with pytest.raises(AmbiguousLookupError, match="(?i)^for function `f`, "):
        f(1, 1)


# We already defined an `A` above. The classes below again need to be in the global
# scope.

dispatch = Dispatcher()


class B(metaclass=abc.ABCMeta):
    @dispatch
    def __init__(self):  # noqa: B027
        pass

    def do(self, x):
        return "B"

    @abc.abstractmethod
    def do_something_else(self, x):
        pass


class C(B):
    @dispatch
    def __init__(self):
        pass

    @dispatch
    def __call__(self):
        return "C"

    @dispatch
    def do(self, x: int):
        return "C"

    @dispatch
    def do_something_else(self, x: int):
        return "C"


def test_call_mro():
    c = C()

    # If method cannot be found, the next in the MRO should be invoked.
    assert c.do(1) == "C"
    assert c.do(1.0) == "B"


def test_call_abstract():
    # Check that ABC still works.
    with pytest.raises(TypeError):
        B()
    c = C()

    # Abstract methods should be ignored.
    assert c.do_something_else(1) == "C"
    with pytest.raises(NotFoundLookupError):
        c.do_something_else(1.0)


def test_call_object():
    with pytest.raises(
        NotFoundLookupError,
        match=r"(?i)^for function `__init__` of `tests.test_function.B`",
    ):
        # Construction requires no arguments. Giving an argument should propagate to
        # `B` and then error.
        C(1)

    with pytest.raises(
        NotFoundLookupError,
        match=r"(?i)^for function `__call__` of `tests.test_function.C`",
    ):
        # Calling requires no arguments.
        C()(1)


def test_call_convert():
    dispatch = Dispatcher()

    @dispatch
    def f(x) -> tuple:
        return x

    assert f(1) == (1,)


def test_invoke():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        return "int"

    @dispatch
    def f(x: float):
        return "float"

    @dispatch
    def f(x: str):
        return "str"

    assert f.invoke(int)(None) == "int"
    assert f.invoke(float)(None) == "float"
    assert f.invoke(str)(None) == "str"


def test_invoke_convert():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int) -> tuple:
        return x

    assert f.invoke(int)(1) == (1,)


def test_invoke_wrapping():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        """Docs"""

    assert f.invoke(int).__name__ == "f"
    assert f.invoke(int).__doc__ == "Docs"


def test_bound():
    dispatch = Dispatcher()

    class A:
        @dispatch
        def do(self, x: int):
            """Docs"""
            return "int"

    assert A().do.__doc__ == "Docs"
    assert A.do.__doc__ == "Docs"

    assert A().do.invoke(int)(1) == "int"
    assert A.do.invoke(A, int)(A(), 1) == "int"

    # Also test that `invoke` is wrapped, like above.
    assert A().do.invoke(int).__doc__ == "Docs"
    assert A.do.invoke(A, int).__doc__ == "Docs"
