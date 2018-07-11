# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import logging

from .dispatcher import Dispatcher

__all__ = ['parametric', 'type_parameter', 'kind', 'Kind']
log = logging.getLogger(__name__)

dispatch = Dispatcher()


@dispatch(object)
def _get_id(x):
    return id(x)


@dispatch({int, float, str, type})
def _get_id(x):
    return x


def parametric(Class):
    """A decorator for parametric classes."""
    subclasses = {}

    if not issubclass(Class, object): # pragma: no cover
        raise RuntimeError('To let {} be a parametric class, it must be a '
                           'new-style class.')

    def __new__(cls, *ps):
        # Convert type parameters.
        ps = tuple(_get_id(p) for p in ps)

        # Only create new subclass if it doesn't exist already.
        if ps not in subclasses:
            def __new__(cls, *args, **kw_args):
                return Class.__new__(cls)

            # Create subclass.
            name = Class.__name__ + '{' + ','.join(str(p) for p in ps) + '}'
            SubClass = type(name,
                            (Class, ParametricClass,),
                            {'__new__': __new__})
            SubClass._type_parameter = ps[0] if len(ps) == 1 else ps
            SubClass.__module__ = Class.__module__

            # Attempt to correct docstring.
            try:
                SubClass.__doc__ = Class.__doc__
            except AttributeError:  # pragma: no cover
                pass

            subclasses[ps] = SubClass
        return subclasses[ps]

    # Create parametric class.
    ParametricClass = type(Class.__name__,
                           Class.__bases__,
                           {'__new__': __new__})
    ParametricClass.__module__ = Class.__module__

    # Attempt to correct docstring.
    try:
        ParametricClass.__doc__ = Class.__doc__
    except AttributeError:  # pragma: no cover
        pass

    return ParametricClass


def type_parameter(x):
    """Get the type parameter of an instance of a parametric type.

    Args:
        x (object): Instance of a parametric type.

    Returns:
        object: Type parameter.
    """
    return x._type_parameter


def kind():
    """Create a parametric wrapper type for dispatch purposes.

    Returns:
        object: New parametric type wrapper.
    """

    @parametric
    class Kind(object):
        def __init__(self, *xs):
            self.xs = xs

        def get(self):
            return self.xs[0] if len(self.xs) == 1 else self.xs

    return Kind


Kind = kind()  #: A default kind provided for convenience.
