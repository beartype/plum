# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import logging
import inspect

from .function import Function
from .signature import Signature as Sig
from .util import get_default
from .type import subclasscheck_cache

__all__ = ['Dispatcher', 'dispatch', 'clear_all_cache']
log = logging.getLogger(__name__)


class Dispatcher(object):
    """A namespace for functions.

    Args:
        in_class (type, optional): Class to which the namespace is associated.
    """

    def __init__(self, in_class=None):
        self._functions = {}
        self._class = in_class

    def __call__(self, *types, **kw_args):
        """Create a decorator for a particular signature.

        Args:
            *types (type): Types of the signatures.
            precedence (int, optional): Precedence of the signature. Defaults to
                `0`.
            return_type (type, optional): Expected return type. Defaults to
                `object.`

        Returns:
            function: Decorator.
        """
        precedence = get_default(kw_args, 'precedence', 0)
        return_type = get_default(kw_args, 'return_type', object)
        return self._create_decorator([Sig(*types)],
                                      precedence=precedence,
                                      return_type=return_type)

    def multi(self, *signatures, **kw_args):
        """Create a decorator for multiple given signatures.

        Args:
            *tuple[type] (type): Signatures.
            precedence (int, optional): Precedence of the signatures. Defaults
                to `0`.
            return_type (type, optional): Expected return type. Defaults to
                `object.`

        Returns:
            function: Decorator.
        """
        precedence = get_default(kw_args, 'precedence', 0)
        return_type = get_default(kw_args, 'return_type', object)
        return self._create_decorator([Sig(*types) for types in signatures],
                                      precedence=precedence,
                                      return_type=return_type)

    def _create_decorator(self, signatures, precedence, return_type):
        def decorator(f):
            name = f.__name__

            # Create a new function only if the function does not already exist.
            if name not in self._functions:
                self._functions[name] = Function(f, in_class=self._class)

            # Register the new method.
            for signature in signatures:
                self._functions[name].register(signature,
                                               f,
                                               precedence,
                                               return_type)

            # Return the function.
            return self._functions[name]

        return decorator

    def annotations(self, precedence=0):  # pragma: no cover
        """Dispatch from annotations.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to
                `0`.

        Returns:
            function: Decorator.
        """

        def decorator(f):
            # Extract specification.
            spec = inspect.getfullargspec(f)

            # Get types of arguments.
            types = []
            for arg in spec.args:
                try:
                    types.append(spec.annotations[arg])
                except KeyError:
                    types.append(object)

            # Get possible varargs.
            if spec.varargs:
                try:
                    types.append([spec.annotations[spec.varargs]])
                except KeyError:
                    types.append([object])

            # Get possible return type.
            try:
                return_type = spec.annotations['return']
            except KeyError:
                return_type = object

            # Assemble signature.
            signature = Sig(*types)

            # Create and call decorator.
            return self._create_decorator([signature],
                                          precedence,
                                          return_type)(f)

        return decorator

    def clear_cache(self):
        """Clear cache."""
        for f in self._functions.values():
            f.clear_cache()


def clear_all_cache():
    """Clear all cache, including the cache of subclass checks. This
    should be called if types are modified."""
    # Clear function caches.
    for f in Function._instances:
        f.clear_cache()

    # Clear subclass check cache.
    subclasscheck_cache.clear()


dispatch = Dispatcher()  #: A default dispatcher for convenience purposes.
