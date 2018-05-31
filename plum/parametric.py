# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import logging

__all__ = ['parametric']
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
                def __init__(self, *args, **kw_args):
                    Class.__init__(self, *args, **kw_args)

                def __new__(cls, *args, **kw_args):
                    return super(Class, cls).__new__(cls, *args, **kw_args)

                name = Class.__name__ + '{' + ','.join(str(p) for p in ps) + '}'
                subclasses[ps] = type(name,
                                      (ParametricClass,),
                                      {'__init__': __init__,
                                       '__new__': __new__})
            return subclasses[ps]

    return ParametricClass
