import pytest

from plum import Dispatcher, List, NotFoundLookupError


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
    assert repr(f) == "<function {} with 1 method(s)>".format(f._f)
    assert f.invoke().__name__ == "f"
    assert f.invoke().__doc__ == "docstring of f"
    assert f.invoke().__module__ == "tests.dispatcher.test_dispatcher"
    assert repr(f.invoke()) == repr(f._f)

    a = A()
    g = a.g

    assert g.__name__ == "g"
    assert g.__doc__ == "docstring of g"
    assert g.__module__ == "tests.dispatcher.test_dispatcher"
    assert repr(g) == f'<function {A._dispatch._functions["g"]._f} with 1 method(s)>'

    assert g.invoke().__name__ == "g"
    assert g.invoke().__doc__ == "docstring of g"
    assert g.invoke().__module__ == "tests.dispatcher.test_dispatcher"
    assert repr(g.invoke()) == repr(A._dispatch._functions["g"]._f)


def test_extension():
    dispatch = Dispatcher()

    @dispatch
    def f():
        return "fallback"

    @f.extend
    def f(x: int):
        return "int"

    @f.extend_multi((str,), (float,))
    def f(x: {str, float}):
        return "str or float"

    assert f() == "fallback"
    assert f(1) == "int"
    assert f("1") == "str or float"
    assert f(1.0) == "str or float"


def test_multi():
    dispatch = Dispatcher()

    @dispatch
    def f(x):
        return "fallback"

    @dispatch.multi((int,), (str,))
    def f(x: {int, str}):
        return "int or str"

    assert f(1) == "int or str"
    assert f("1") == "int or str"
    assert f(1.0) == "fallback"


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
    def f(x: {int, str, float}):
        return "int, str, or float"

    assert f() == "fallback"
    assert f(1) == "int"
    assert f("1") == "str"
    assert f(1.0) == "int, str, or float"
    assert f.invoke()() == "fallback"
    assert f.invoke(int)("1") == "int"
    assert f.invoke(str)(1) == "str"
    assert f.invoke(float)(1) == "int, str, or float"
    assert f.invoke({int, str})(1) == "int, str, or float"
    assert f.invoke({int, str, float})(1) == "int, str, or float"


def test_invoke_inheritance():
    class A:
        def do(self, x):
            return "fallback"

    class B(A):
        _dispatch = Dispatcher()

        @_dispatch
        def do(self, x: int):
            return "int"

    class C(B):
        _dispatch = Dispatcher()

        @_dispatch
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


def test_context():
    # Automatically determine context if `in_class` is not set.

    dispatch = Dispatcher()

    class A:
        @dispatch
        def do(self):
            pass

    a = A()
    a.do()

    keys = set(dispatch._functions.keys())
    assert keys == {"tests.dispatcher.test_dispatcher.test_context.<locals>.A.do"}

    # This should not happen if `in_class` is set.

    class A:
        dispatch = Dispatcher()

        @dispatch
        def do(self):
            pass

    a = A()
    a.do()

    assert A.dispatch._functions.keys() == {"do"}

    # It should also not happen if `context` is explicitly set.

    dispatch = Dispatcher()

    class A:
        @dispatch(context="context")
        def do(self):
            pass

    a = A()
    a.do()

    assert dispatch._functions.keys() == {"context.do"}


def test_class():
    class Other:
        pass

    # Automatically determine class if `in_class` is not set.

    dispatch = Dispatcher()

    class A:
        @dispatch
        def do(self):
            pass

    a = A()
    a.do()

    assert len(dispatch._functions) == 1
    assert list(dispatch._functions.values())[0]._class.get_types() == (A,)

    # This should not happen if `in_class` is set.

    dispatch = Dispatcher(in_class=Other)

    class A:
        @dispatch
        def do(self):
            pass

    a = A()
    a.do()

    assert len(dispatch._functions) == 1
    assert list(dispatch._functions.values())[0]._class.get_types() == (Other,)

    # It should also not happen if `in_class` is explicitly set.

    dispatch = Dispatcher(in_class=Other)

    class OtherTwo:
        pass

    class A:
        @dispatch(in_class=OtherTwo)
        def do(self):
            pass

    a = A()
    a.do()

    assert len(dispatch._functions) == 1
    assert list(dispatch._functions.values())[0]._class.get_types() == (OtherTwo,)


def test_context_multi():
    # Automatically determine context if `in_class` is not set.

    dispatch = Dispatcher()

    class A:
        @dispatch.multi((object,))
        def do(self):
            pass

    a = A()
    a.do()

    keys = set(dispatch._functions.keys())
    assert keys == {"tests.dispatcher.test_dispatcher.test_context_multi.<locals>.A.do"}

    # This should not happen if `in_class` is set.

    class A:
        dispatch = Dispatcher()

        @dispatch.multi((object,))
        def do(self):
            pass

    a = A()
    a.do()

    assert A.dispatch._functions.keys() == {"do"}

    # It should also not happen if `context` is explicitly set.

    dispatch = Dispatcher()

    class A:
        @dispatch.multi((object,), context="context")
        def do(self):
            pass

    a = A()
    a.do()

    assert dispatch._functions.keys() == {"context.do"}


def test_class_multi():
    class Other:
        pass

    # Automatically determine class if `in_class` is not set.

    dispatch = Dispatcher()

    class A:
        @dispatch.multi((object,))
        def do(self):
            pass

    a = A()
    a.do()

    assert len(dispatch._functions) == 1
    assert list(dispatch._functions.values())[0]._class.get_types() == (A,)

    # This should not happen if `in_class` is set.

    dispatch = Dispatcher(in_class=Other)

    class A:
        @dispatch.multi((object,))
        def do(self):
            pass

    a = A()
    a.do()

    assert len(dispatch._functions) == 1
    assert list(dispatch._functions.values())[0]._class.get_types() == (Other,)

    # It should also not happen if `in_class` is explicitly set.

    dispatch = Dispatcher(in_class=Other)

    class OtherTwo:
        pass

    class A:
        @dispatch.multi((object,), in_class=OtherTwo)
        def do(self):
            pass

    a = A()
    a.do()

    assert len(dispatch._functions) == 1
    assert list(dispatch._functions.values())[0]._class.get_types() == (OtherTwo,)
