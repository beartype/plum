# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import logging

__all__ = ['parametric', 'type_parameter', 'Kind']
log = logging.getLogger(__name__)


def parametric(Class):
    """A decorator for parametric classes."""
    subclasses = {}

    if not issubclass(Class, object):
        raise RuntimeError('To let {} be a parametric class, it must be a '
                           'new-style class.')

    class ParametricClass(Class):
        def __new__(cls, *ps):
            try:
                hash(ps)
            except TypeError:
                raise TypeError('Type parameters must be hashable.')

            if ps not in subclasses:
                def __new__(cls, *args, **kw_args):
                    return Class.__new__(cls)

                name = Class.__name__ + '{' + ','.join(str(p) for p in ps) + '}'
                SubClass = type(name, (ParametricClass,), {'__new__': __new__})
                SubClass._type_parameter = ps[0] if len(ps) == 1 else ps
                subclasses[ps] = SubClass
            return subclasses[ps]

    return ParametricClass


def type_parameter(x):
    """Get the type parameter of an instance of a parametric type.

    Args:
        x (instance): Instance of a parametric type.
    """
    return x._type_parameter


@parametric
class Kind(object):
    """A parametric wrapper type for dispatch purposes."""

    def __init__(self, *xs):
        self.xs = xs

    def get(self):
        return self.xs[0] if len(self.xs) == 1 else self.xs

