# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from plum import Dispatcher, Referentiable, Self

from . import eq, raises


def test_double_definition():
    dispatch = Dispatcher()

    @dispatch(int)
    def f(x): pass

    @dispatch(int)
    def f(x): pass

    yield raises, RuntimeError, lambda: f(1)


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

    yield eq, f.__name__, 'f'
    yield eq, f.__doc__, 'docstring of f'
    yield eq, f.__module__, 'tests.test_dispatcher'
    yield eq, repr(f), '<function {} with 1 method(s)>'.format(f._f)
    yield eq, f.invoke().__name__, 'f'
    yield eq, f.invoke().__doc__, 'docstring of f'
    yield eq, f.invoke().__module__, 'tests.test_dispatcher'
    yield eq, repr(f.invoke()), repr(f._f)

    a = A()
    g = a.g

    yield eq, g.__name__, 'g'
    yield eq, g.__doc__, 'docstring of g'
    yield eq, g.__module__, 'tests.test_dispatcher'
    yield eq, repr(g), '<function {} with 1 method(s)>' \
                       ''.format(A._dispatch._functions['g']._f)
    yield eq, g.invoke().__name__, 'g'
    yield eq, g.invoke().__doc__, 'docstring of g'
    yield eq, g.invoke().__module__, 'tests.test_dispatcher'
    yield eq, repr(g.invoke()), repr(A._dispatch._functions['g']._f)


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

    yield eq, f(), 'fallback'
    yield eq, f(1), 'int'
    yield eq, f('1'), 'str or float'
    yield eq, f(1.0), 'str or float'


def test_multi():
    dispatch = Dispatcher()

    @dispatch(object)
    def f(x):
        return 'fallback'

    @dispatch.multi([int], [str])
    def f(x):
        return 'int or str'

    yield eq, f(1), 'int or str'
    yield eq, f('1'), 'int or str'
    yield eq, f(1.), 'fallback'


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

    yield eq, f(), 'fallback'
    yield eq, f(1), 'int'
    yield eq, f('1'), 'str'
    yield eq, f(1.0), 'int, str, or float'
    yield eq, f.invoke()(), 'fallback'
    yield eq, f.invoke(int)('1'), 'int'
    yield eq, f.invoke(str)(1), 'str'
    yield eq, f.invoke(float)(1), 'int, str, or float'
    yield eq, f.invoke({int, str})(1), 'int, str, or float'
    yield eq, f.invoke({int, str, float})(1), 'int, str, or float'


# TODO:
#   If the following classes are defined inside `test_invoke_inheritance`,
#   `Referentiable.__subclasses__()` in `test_type.test_self` does not add `A`
#   to the end in Python 2.7. Why?

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


def test_invoke_inheritance():
    c = C()

    # Test bound calls.
    yield eq, c.do.invoke(str)('1'), 'str'
    yield eq, c.do.invoke(int)(1), 'int'
    yield eq, c.do.invoke(float)(1.0), 'fallback'

    # Test unbound calls.
    yield eq, C.do.invoke(str)(c, '1'), 'str'
    yield eq, C.do.invoke(int)(c, 1), 'int'
    yield eq, C.do.invoke(float)(c, 1.0), 'fallback'
