# -*- coding: utf-8 -*-

from __future__ import division, print_function, absolute_import

import abc
import logging
import six

__all__ = ['ResolutionError',
           'Resolvable',
           'Promise',
           'Referentiable',
           'Reference']
log = logging.getLogger(__name__)


class ResolutionError(RuntimeError):
    """Object could not be resolved."""


class Resolvable(six.with_metaclass(abc.ABCMeta, object)):
    """An object that can be resolved and compared."""

    @abc.abstractmethod
    def resolve(self):
        """Resolve the object.

        Returns:
            Promised object.
        """


class Promise(Resolvable):
    """An object that is promised to be resolvable when asked for."""

    def __init__(self):
        self._obj = None

    def deliver(self, obj):
        """Deliver the promise.

        Args:
            obj: The object to deliver.
        """
        self._obj = obj

    def resolve(self):
        if self._obj is None:
            raise ResolutionError('Promise was not kept.')
        else:
            return self._obj


class ReferentiableTracker(type):
    """Metaclass that tracks referentiables."""
    referentiables = []

    def __init__(cls, name, bases, dct):
        ReferentiableTracker.referentiables.append(cls)
        type.__init__(cls, name, bases, dct)


class Referentiable(six.with_metaclass(ReferentiableTracker, object)):
    """A class that can be referenced through :class:`.resolvable.Reference`."""


class Reference(Resolvable):
    """Resolves to the last subclass of :class:`.resolvable.Referentiable`."""

    def __init__(self):
        self.pos = len(ReferentiableTracker.referentiables)

    def resolve(self):
        referentiables = Referentiable.referentiables
        if len(referentiables) - 1 < self.pos:
            raise ResolutionError(
                'Requesting referentiable {}, whereas only {} exist(s).'
                ''.format(self.pos + 1, len(referentiables)))
        else:
            return referentiables[self.pos]
