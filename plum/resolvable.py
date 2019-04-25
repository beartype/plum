# -*- coding: utf-8 -*-

from __future__ import division, print_function, absolute_import

import abc
import logging

__all__ = ['ResolutionError',
           'Resolvable',
           'Promise',
           'Referentiable',
           'Reference']
log = logging.getLogger(__name__)


class ResolutionError(RuntimeError):
    """Object could not be resolved."""


class Resolvable(object):
    """An object that can be resolved and compared."""

    __metaclass__ = abc.ABCMeta

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


class Referentiable(object):
    """A class that can be referenced through :class:`.resolvable.Reference`."""


class Reference(Resolvable):
    """Resolves to the last subclass of :class:`.resolvable.Referentiable`."""

    def __init__(self):
        self.pos = len(Referentiable.__subclasses__())

    def resolve(self):
        subclasses = Referentiable.__subclasses__()
        if len(subclasses) - 1 < self.pos:
            raise ResolutionError(
                'Requesting subclass {} of Referentiable, whereas only {} '
                'exist(s).'.format(self.pos + 1, len(subclasses)))
        else:
            return subclasses[self.pos]
