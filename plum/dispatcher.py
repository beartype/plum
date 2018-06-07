# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import logging

from .function import Function
from .tuple import Tuple

__all__ = ['Dispatcher', 'dispatch']
log = logging.getLogger(__name__)


class Dispatcher(object):
    """A namespace for functions.

    Args:
        in_class (type, optional): Class to which the namespace is associated.
    """

    def __init__(self, in_class=None):
        self._functions = {}
        self._class = in_class

    def __call__(self, *types):
        return self._create_decorator([Tuple(*types)])

    def multi(self, *signatures):
        return self._create_decorator([Tuple(*types) for types in signatures])

    def _create_decorator(self, signatures):
        def decorator(f):
            name = f.__name__

            # Create a new function if the function does not already exist.
            if name not in self._functions:
                self._functions[name] = Function(name, in_class=self._class)

            # Register the new method.
            for signature in signatures:
                self._functions[name].register(signature, f)

            # Return the function.
            return self._functions[name]

        return decorator

    def clear_cache(self):
        """Clear all cache."""
        for f in self._functions.values():
            f.clear_cache()


dispatch = Dispatcher()
