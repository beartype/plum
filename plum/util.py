# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import abc
import logging

__all__ = ['multihash', 'Comparable', 'get_default']
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
