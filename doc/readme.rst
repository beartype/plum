`Plum: Multiple Dispatch in Python <https://github.com/wesselb/plum>`__
=======================================================================

|Build| |Coverage Status| |Latest Docs|

Everybody likes multiple dispatch, just like everybody likes plums.

Examples
--------

Parametric Classes
~~~~~~~~~~~~~~~~~~

.. code:: python

    from plum import dispatch, parametric

    @parametric
    class A(object):  # Must be a new-style class!
        pass
        
    @dispatch(A)
    def f(x):
        return 'fallback'
        
    @dispatch(A(1))
    def f(x):
        return '1'
        
    @dispatch(A(2))
    def f(x):
        return '2'

.. code:: python

    >>> A
    plum.parametric.parametric.<locals>.ParametricClass
    >>> A(1)
    plum.parametric.A{1}
    >>> issubclass(A(1), A)
    True
    >>> A(1)()
    <plum.parametric.A{1} at 0x<snip>>
    >>> f(A(1)())
    '1'
    >>> f(A(2)())
    '2'
    >>> f(A(3)())
    'fallback'

Variable Types
~~~~~~~~~~~~~~

.. code:: python

    from plum import dispatch

    @dispatch(int)
    def f(x):
        print('single argument')

    @dispatch(int, [int])
    def f(x, *xs):
        print('multiple arguments')

::

    >>> f(1)
    single argument
    >>> f(1, 2)
    multiple arguments
    >>> f(1, 2, 3)
    multiple arguments

Union Types
~~~~~~~~~~~

.. code:: python

    from plum import dispatch

    @dispatch(object)
    def f(x):
        print('fallback')

    @dispatch({int, str})
    def f(x):
        print('int or str')

::

    >>> f(1)
    int or str
    >>> f('1')
    int or str
    >>> f(1.0)
    fallback

Inheritance
~~~~~~~~~~~

.. code:: python

    from plum import Dispatcher, Referentiable, Self

    class Kernel(Referentiable):
        dispatch = Dispatcher(in_class=Self)

        @dispatch(Self)
        def __add__(self, other):
            return 'kernel'

    class StationaryKernel(Kernel, Referentiable):
        dispatch = Dispatcher(in_class=Self)

        @dispatch(Self)
        def __add__(self, other):
            return 'stationary kernel'

    kernel = Kernel()
    stationary_kernel = StationaryKernel()

::

    >>> kernel + kernel
    'kernel'
    >>> kernel + stationary_kernel
    'kernel'
    >>> stationary_kernel + kernel
    'kernel'
    >>> stationary_kernel + stationary_kernel
    'stationary kernel'

.. |Build| image:: https://travis-ci.org/wesselb/plum.svg?branch=master
   :target: https://travis-ci.org/wesselb/plum
.. |Coverage Status| image:: https://coveralls.io/repos/github/wesselb/plum/badge.svg?branch=master
   :target: https://coveralls.io/github/wesselb/plum?branch=master
.. |Latest Docs| image:: https://img.shields.io/badge/docs-latest-blue.svg
   :target: https://plum-docs.readthedocs.io/en/latest
