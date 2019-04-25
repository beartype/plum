# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import abc
import logging

__all__ = ['multihash', 'Comparable', 'get_default', 'Wrapped']
log = logging.getLogger(__name__)


def multihash(*args):
    """Multi-argument order-sensitive hash.

    Args:
        *args: Objects to hash.

    Returns:
        int: Hash.
    """
    return hash(args)


class Comparable(object):
    """A mixin that makes instances of the class comparable.

    Requires the subclass to just implement `__le__`.
    """
    __metaclass__ = abc.ABCMeta

    def __eq__(self, other):
        return self <= other <= self

    def __ne__(self, other):
        return not self == other

    @abc.abstractmethod
    def __le__(self, other):
        pass  # pragma: no cover

    def __lt__(self, other):
        return self <= other and self != other

    def __ge__(self, other):
        return other.__le__(self)

    def __gt__(self, other):
        return self >= other and self != other

    def is_comparable(self, other):
        """Check whether this object is comparable with another one.

        Args:
            other (:class:`.util.Comparable`): Object to check comparability
                with.

        Returns:
            bool: `True` if the object is comparable with `other` and `False`
                otherwise.
        """
        return self < other or self == other or self > other


def get_default(dictionary, key, default):
    """Get a value from a dictionary, assuming a default value.

    Args:
        dictionary (dict): Dictionary.
        key (hashable): Key of value to get.
        default (object): Default value, in case the key is not in the
            dictionary.

    Returns:
        object: Value associated to key or the default value.
    """
    try:
        return dictionary[key]
    except KeyError:
        return default


class Wrapped(object):
    """Wrap a callable, copying metadata.

    Args:
        obj (object): Callable to wrap.
        prepend_args (tuple, optional): Arguments to prepend to any call.
            Defaults to not prepending any arguments.
        processing_fun (function, optional): Function to apply to the result of
            any call. Defaults to the identity function.
    """

    def __init__(self, obj, prepend_args=(), processing_fun=lambda x: x):
        self._obj = obj
        self._prepend_args = prepend_args
        self._processing_fun = processing_fun

        # Copy metadata.
        self.__name__ = obj.__name__
        self.__doc__ = obj.__doc__
        self.__module__ = obj.__module__

    def __call__(self, *args, **kw_args):
        result = self._obj(*(self._prepend_args + args), **kw_args)
        return self._processing_fun(result)

    def __getattr__(self, item):
        return getattr(self._obj, item)
