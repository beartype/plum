import abc
import os
import textwrap
import typing

import pytest

from plum import Dispatcher
from plum.function import Function, _convert, _owner_transfer
from plum.method import Method
from plum.resolver import (
    AmbiguousLookupError,
    NotFoundLookupError,
    _change_function_name,
)
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

    assert repr(f) == (
        f"<multiple-dispatch function {f.__qualname__}"
        f" (with 0 registered and 2 pending method(s))>"
    )

    # Register all methods.
    assert f(1) == "int"

    assert repr(f) == (
        f"<multiple-dispatch function {f.__qualname__}"
        f" (with 2 registered and 0 pending method(s))>"
    )

    @dispatch
    def f(x: float):
        return "float"

    assert repr(f) == (
        f"<multiple-dispatch function {f.__qualname__}"
        f" (with 2 registered and 1 pending method(s))>"
    )

    # Again register all methods.
    assert f(1) == "int"

    assert repr(f) == (
        f"<multiple-dispatch function {f.__qualname__}"
        " (with 3 registered and 0 pending method(s))>"
    )


# `A` needs to be in the global scope for owner resolution to work.


class A:
    pass


def test_owner():
    def f(x):
        pass

    assert Function(f).owner is None
    assert Function(f, owner="A").owner is A


def test_resolve_method_with_cache_no_arguments():
    def f(x):
        pass

    with pytest.raises(ValueError, match="`args` and `types` cannot both be `None`"):
        Function(f)._resolve_method_with_cache()


@pytest.fixture()
def owner_transfer():
    # Save and clear.
    before = dict(_owner_transfer)
    _owner_transfer.clear()

    yield _owner_transfer

    # Restore.
    _owner_transfer.clear()
    _owner_transfer.update(before)


def test_owner_transfer(owner_transfer):
    def f(x):
        pass

    class B:
        pass

    # Transfer once.
    owner_transfer[A] = B
    assert Function(f, owner="A").owner is B

    class C:
        pass

    # Transfer twice.
    owner_transfer[B] = C
    assert Function(f, owner="A").owner is C


def test_functionmeta():
    assert Function.__doc__ == Function._class_doc


def test_doc(monkeypatch):
    def f(x: int):
        """
        Process an int.
        """

    def f2(x: float):
        """Process a float.

        Args:
            x (float): Argument.
        """

    # Test the following:
    #   (1) the self-exclusion mechanism,
    #   (2) single-line original docstring,
    #   (3) the trimming of whitespace of the original docstring, and
    #   (4) the replacement of `<separator>` by lines of the right length.
    g = Function(f).dispatch(f)
    assert g.__doc__ == "Process an int."
    g.dispatch(f2)
    expected_doc = """
    Process an int.

    ------------------------

    f(x: float)

    Process a float.

    Args:
        x (float): Argument.
    """
    assert g.__doc__ == textwrap.dedent(expected_doc).strip()

    def f(x: int):
        """
        Process an int.

        Args:
            x (int): A very long argument.
        """

    # Test multi-line original docstring.
    g = Function(f).dispatch(f)
    expected_doc = """
    Process an int.

    Args:
        x (int): A very long argument.
    """
    assert g.__doc__ == textwrap.dedent(expected_doc).strip()
    g.dispatch(f2)
    expected_doc = """
    Process an int.

    Args:
        x (int): A very long argument.

    ----------------------------------

    f(x: float)

    Process a float.

    Args:
        x (float): Argument.
    """
    assert g.__doc__ == textwrap.dedent(expected_doc).strip()

    def f(x: int):
        pass

    # Test empty original docstring.
    g = Function(f).dispatch(f)
    assert g.__doc__ is None
    g.dispatch(f2)
    expected_doc = """
    ------------------------

    f(x: float)

    Process a float.

    Args:
        x (float): Argument.
    """
    assert g.__doc__ == textwrap.dedent(expected_doc).strip()


def test_simple_doc(monkeypatch):
    @dispatch
    def f(x: int):
        """First."""

    @dispatch
    def f(x: str):
        """Second."""

    monkeypatch.setitem(os.environ, "PLUM_SIMPLE_DOC", "1")
    assert f.__doc__ == "First."

    monkeypatch.setitem(os.environ, "PLUM_SIMPLE_DOC", "0")
    expected_doc = """
    First.

    -----------

    f(x: str)

    Second.
    """
    assert f.__doc__ == textwrap.dedent(expected_doc).strip()


def test_methods():
    dispatch = Dispatcher()

    def f(x: int):
        pass

    method1 = Method(f, Signature(int), function_name="f")
    f_dispatch = dispatch(f)

    def f(x: float):
        pass

    method2 = Method(f, Signature(float), function_name="f")
    dispatch(f)

    methods = [method1, method2]

    assert list(f_dispatch.methods) == methods


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
    assert f._resolver.resolve(("1",)).signature.precedence == 1


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
    assert f._resolver.resolve(("1",)).signature.precedence == 1

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


def test_call_dispatch_error():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int, y):
        pass

    @dispatch
    def f(x, y: int):
        pass

    with pytest.raises(
        NotFoundLookupError,
        match="(?i)^`f\\('1', '1'\\)` could not be resolved\\.\n\nClosest",
    ):
        f("1", "1")

    with pytest.raises(
        AmbiguousLookupError,
        match="(?i)^`f\\(1, 1\\)` is ambiguous\\.\n\nCandidates:",
    ):
        f(1, 1)


# We already defined an `A` above. The classes below again need to be in the global
# scope.

dispatch = Dispatcher()


class B(metaclass=abc.ABCMeta):
    @dispatch  # noqa: B027
    def __init__(self):
        pass

    def do(self, x):
        return "B"

    @abc.abstractmethod
    def do_something_else(self, x):
        pass


# Put a class in the middle of the two to make sure that MRO resolution works well.


class Inbetween(B):
    pass


class C(Inbetween):
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

    @dispatch
    def __le__(self, other: int):
        return 1


def test_call_mro():
    c = C()

    # If method cannot be found, the next in the MRO should be invoked.
    assert c.do(1) == "C"
    assert c.do(1.0) == "B"

    # Test a dunder method.
    assert (c <= 2) == 1
    with pytest.raises(
        NotFoundLookupError,
        match=r"(?i)^`C.__le__\(.+\)` could not be\s+resolved",
    ):
        c <= "2"  # noqa


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
        match=r"(?is)^`B.__init__\(.+\)` could not be\s+resolved",
    ):
        # Construction requires no arguments. Giving an argument should propagate to
        # `B` and then error.
        C(1)

    with pytest.raises(
        NotFoundLookupError,
        match=r"(?is)^`C.__call__\(.+\)` could not be\s+resolved",
    ):
        # Calling requires no arguments.
        C()(1)


dispatch = Dispatcher()


class D(type):
    @dispatch
    def __call__(self, x: str):
        pass


class E(D):
    @dispatch
    def __init__(self, name: str, bases: typing.Tuple[type], methods: dict):
        pass

    @dispatch
    def __call__(self):
        pass


def test_call_type():
    """Exactly like :func:`test_call_object`."""

    class A:
        pass

    with pytest.raises(
        NotFoundLookupError,
        match=r"(?is)^`E\.__init__\(.+\)` could\s+not be resolved",
    ):
        E("Test", (A, object), {})  # Must have exactly one base.

    with pytest.raises(
        NotFoundLookupError,
        match=r"(?is)^`D\.__call__\(.+\)` could\s+not be resolved",
    ):
        # The call method will be tried at :class:`D` and only then error.
        E("Test", (object,), {})(1)


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
