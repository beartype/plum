# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import pytest

from plum import Dispatcher, Referentiable, Self, List


def test_double_definition():
    dispatch = Dispatcher()

    @dispatch(int)
    def f(x): pass

    @dispatch(int)
    def f(x): pass

    with pytest.raises(RuntimeError):
        f(1)


def test_metadata_and_printing():
    dispatch = Dispatcher()

    class A(Referentiable):
        _dispatch = Dispatcher(in_class=Self)

        @_dispatch()
        def g(self):
            """docstring of g"""

    @dispatch()
    def f():
        """docstring of f"""

    assert f.__name__ == 'f'
    assert f.__doc__ == 'docstring of f'
    assert f.__module__ == 'tests.dispatcher.test_dispatcher'
    assert repr(f) == '<function {} with 1 method(s)>'.format(f._f)
    assert f.invoke().__name__ == 'f'
    assert f.invoke().__doc__ == 'docstring of f'
    assert f.invoke().__module__ == 'tests.dispatcher.test_dispatcher'
    assert repr(f.invoke()) == repr(f._f)

    a = A()
    g = a.g

    assert g.__name__ == 'g'
    assert g.__doc__ == 'docstring of g'
    assert g.__module__ == 'tests.dispatcher.test_dispatcher'
    assert repr(g) == '<function {} with 1 method(s)>' \
                      ''.format(A._dispatch._functions['g']._f)
    assert g.invoke().__name__ == 'g'
    assert g.invoke().__doc__ == 'docstring of g'
    assert g.invoke().__module__ == 'tests.dispatcher.test_dispatcher'
    assert repr(g.invoke()) == repr(A._dispatch._functions['g']._f)


def test_extension():
    dispatch = Dispatcher()

    @dispatch()
    def f():
        return 'fallback'

    @f.extend(int)
    def f(x):
        return 'int'

    @f.extend_multi((str,), (float,))
    def f(x):
        return 'str or float'

    assert f() == 'fallback'
    assert f(1) == 'int'
    assert f('1') == 'str or float'
    assert f(1.0) == 'str or float'


def test_multi():
    dispatch = Dispatcher()

    @dispatch(object)
    def f(x):
        return 'fallback'

    @dispatch.multi([int], [str])
    def f(x):
        return 'int or str'

    assert f(1) == 'int or str'
    assert f('1') == 'int or str'
    assert f(1.) == 'fallback'


def test_invoke():
    dispatch = Dispatcher()

    @dispatch()
    def f():
        return 'fallback'

    @dispatch(int)
    def f(x):
        return 'int'

    @dispatch(str)
    def f(x):
        return 'str'

    @dispatch({int, str, float})
    def f(x):
        return 'int, str, or float'

    assert f() == 'fallback'
    assert f(1) == 'int'
    assert f('1') == 'str'
    assert f(1.0) == 'int, str, or float'
    assert f.invoke()() == 'fallback'
    assert f.invoke(int)('1') == 'int'
    assert f.invoke(str)(1) == 'str'
    assert f.invoke(float)(1) == 'int, str, or float'
    assert f.invoke({int, str})(1) == 'int, str, or float'
    assert f.invoke({int, str, float})(1) == 'int, str, or float'


def test_invoke_inheritance():
    class A(object):
        def do(self, x):
            return 'fallback'

    class B(A, Referentiable):
        _dispatch = Dispatcher(in_class=Self)

        @_dispatch(int)
        def do(self, x):
            return 'int'

    class C(B, Referentiable):
        _dispatch = Dispatcher(in_class=Self)

        @_dispatch(str)
        def do(self, x):
            return 'str'

    c = C()

    # Test bound calls.
    assert c.do.invoke(str)('1') == 'str'
    assert c.do.invoke(int)(1) == 'int'
    assert c.do.invoke(float)(1.0) == 'fallback'

    # Test unbound calls.
    assert C.do.invoke(str)(c, '1') == 'str'
    assert C.do.invoke(int)(c, 1) == 'int'
    assert C.do.invoke(float)(c, 1.0) == 'fallback'


def test_parametric_tracking():
    dispatch = Dispatcher()

    @dispatch(int)
    def f(x):
        pass

    assert not f._parametric
    f(1)
    assert not f._parametric

    @dispatch(List(int))
    def f(x):
        pass

    assert not f._parametric
    f(1)
    assert f._parametric
