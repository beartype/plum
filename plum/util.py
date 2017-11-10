# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import abc


def multihash(*args):
    """Multi-argument order-sensitive hash."""
    return hash(args)


class Namespace(object):
    """A general-purpose namespace."""


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
        pass

    def __lt__(self, other):
        return self <= other and self != other

    def __ge__(self, other):
        return other.__le__(self)

    def __gt__(self, other):
        return self >= other and self != other

    def is_comparable(self, other):
        """Check whether this object is comparable with another one."""
        return self < other or self == other or self > other

