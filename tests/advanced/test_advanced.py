import collections
import math
import operator
from functools import wraps
from typing import Union

import pytest

from plum import Dispatcher, Function, NotFoundLookupError


def test_keywords():
    dispatch = Dispatcher()

    @dispatch
    def f(x: int, *, option=None):
        return x

    assert f(2) == 2
    assert f(2, option=None) == 2
    with pytest.raises(NotFoundLookupError):
        f(2, None)


def test_defaults():
    dispatch = Dispatcher()

    y_default = 3

    @dispatch
    def f(x: int, y: int = y_default, *, option=None):
        return y

    @dispatch
    def f(x: float, y: int = y_default, *, option=None):
        return y**2

    assert f(2) == y_default
    assert f(2, option=None) == y_default
    assert f(2, 4) == 4
    assert f(2, y=4) == 4
    assert f(2, y=4, option=None) == 4

    assert f(2.0) == y_default**2
    assert f(2.0, y=4) == 4**2

    with pytest.raises(NotFoundLookupError):
        f(2, 4.0)

    with pytest.raises(NotFoundLookupError):
        f(2, 4.0, option=2)

    # Check that a wrong default type is caught.

    with pytest.raises(TypeError):

        @dispatch
        def f_wrong_default(x: int, y: float = y_default):
            return y

        f_wrong_default._resolve_pending_registrations()

    # Remove this function from global tracking. Otherwise, it might interfere with
    # other tests.
    Function._instances.pop(-1)

    # Try multiple arguments.

    @dispatch
    def g(x: int, y: int = y_default, z: float = 3.0):
        return (y, z)

    assert g(2) == (y_default, 3.0)


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
        @dispatch
        def g(self):
            """Docs of g"""

    @dispatch
    def f():
        """Docs of f"""

    assert f.__name__ == "f"
    assert f.__qualname__ == "test_metadata_and_printing.<locals>.f"
    assert f.__module__ == "tests.advanced.test_advanced"
    assert f.__doc__ == "Docs of f"

    assert f.invoke().__name__ == "f"
    assert f.invoke().__qualname__ == "test_metadata_and_printing.<locals>.f"
    assert f.invoke().__module__ == "tests.advanced.test_advanced"
    assert f.invoke().__doc__ == "Docs of f"

    for g, ts in [(A().g, ()), (A.g, (A,))]:
        assert g.__name__ == "g"
        assert g.__qualname__ == "test_metadata_and_printing.<locals>.A.g"
        assert g.__module__ == "tests.advanced.test_advanced"
        assert g.__doc__ == "Docs of g"

        assert g.invoke(*ts).__name__ == "g"
        assert g.invoke(*ts).__qualname__ == "test_metadata_and_printing.<locals>.A.g"
        assert g.invoke(*ts).__module__ == "tests.advanced.test_advanced"
        assert g.invoke(*ts).__doc__ == "Docs of g"


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


def test_invoke_in_class():
    c = C()

    # Test bound calls.
    assert c.do.invoke(str)("1") == "str"
    assert c.do.invoke(int)(1) == "int"
    assert c.do.invoke(float)(1.0) == "fallback"

    # Test unbound calls.
    assert C.do.invoke(C, str)(c, "1") == "str"
    assert C.do.invoke(C, int)(c, 1) == "int"
    assert C.do.invoke(C, float)(c, 1.0) == "fallback"


def test_unassignable_annotations():
    class A:
        @classmethod
        def create(cls):
            pass

    # `A.create` will have an attribute `__annotations__`, but it cannot be assigned.

    f = Function(lambda: None)
    f.dispatch(A.create)
    f()


@pytest.mark.parametrize(
    "f, x, res",
    [
        (operator.attrgetter("x"), collections.namedtuple("NamedTuple", "x")(x=1), 1),
        (operator.itemgetter("x"), {"x": 1}, 1),
        (math.sqrt, 4, 2),
    ],
)
def test_strange_functions(f, x, res):
    g = Function(lambda: None)
    g.dispatch(f)
    assert g(x) == res


class A2:
    @dispatch
    def f(self, x: "A2"):
        return "self"

    @dispatch
    def f(self, x: str):
        return "str"


def test_self_reference():
    a = A2()
    assert a.f(a) == "self"
    assert a.f("1") == "str"


class A3:
    @dispatch
    def f(self, x: int):
        return "int1"

    class A:
        @dispatch
        def f(self, x: int):
            return "int2"

        @dispatch
        def f(self, x: str):
            return "str2"

    @dispatch
    def f(self, x: str):
        return "str1"


def test_nested_class():
    a1 = A3()
    a2 = A3.A()

    assert a1.f(1) == "int1"
    assert a1.f("1") == "str1"

    assert a2.f(1) == "int2"
    assert a2.f("1") == "str2"


def dec(f):
    @wraps(f)
    def f_wrapped(*args, **kw_args):
        return f(*args, **kw_args)

    return f_wrapped


def test_decorator():
    dispatch = Dispatcher()

    @dec
    @dispatch
    @dec
    def g(x: int):
        return "int"

    @dec
    @dispatch
    @dec
    def g(x: str):
        return "str"

    assert g(1) == "int"
    assert g("1") == "str"


class A4:
    @dec
    @dispatch
    @dec
    def f(self, x: int):
        return "int"

    @dec
    @dispatch
    @dec
    def f(self, x: str):
        return "str"


def test_decorator_in_class():
    a = A4()

    assert a.f(1) == "int"
    assert a.f("1") == "str"


class A5:
    @property
    def name(self):
        return "name"

    @name.setter
    @dispatch
    def name(self, x: str):
        return "str"


def test_property():
    a = A5()

    assert a.name == "name"
    a.name = "another name"
    with pytest.raises(NotFoundLookupError):
        a.name = 1


def test_none():
    dispatch = Dispatcher()

    @dispatch
    def f(x: None) -> None:
        return x

    assert f(None) is None
