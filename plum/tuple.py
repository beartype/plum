# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import logging

from .type import as_type, VarArgs
from .util import Comparable, multihash

__all__ = ['Tuple']
log = logging.getLogger(__name__)


class Tuple(Comparable):
    """Tuple.

    Args:
        *types (type): Types of the arguments.
    """

    def __init__(self, *types):
        # Ensure that all types are types.
        self.types = tuple(map(as_type, types))

        # Ensure that only the last type possibly represents varargs.
        if any([isinstance(t, VarArgs) for t in self.types[:-1]]):
            raise TypeError('Only the last type can represent varargs.')

    def __repr__(self):
        return '({})'.format(', '.join(map(repr, self.types)))

    def __hash__(self):
        return multihash(Tuple, *self.types)

    def __len__(self):
        return len(self.base)

    def apply_binary_operator(self, operator, other):
        """Apply a binary operator to this :class:`.tuple.Tuple` and another."""
        if not self.is_compatible(other):
            return False
        return all([operator(x, y) for x, y
                    in zip(self.expand_varargs_to(other),
                           other.expand_varargs_to(self))])

    def expand_varargs_to(self, tup):
        """Expand types to a given :class:`.tuple.Tuple`."""
        if self.has_varargs():
            expansion_size = max(len(tup) - len(self), 0)
            types = self.base + self.types[-1].expand(expansion_size)
            log.debug('Expanded {} as {} for {}.'.format(self, types, tup))
            return types
        else:
            return self.base

    def __le__(self, other):
        if self.has_varargs() and not other.has_varargs():
            return False
        elif self.has_varargs() and other.has_varargs():
            return (self.varargs_type <= other.varargs_type and
                    self.apply_binary_operator(lambda x, y: x <= y, other))
        else:
            return self.apply_binary_operator(lambda x, y: x <= y, other)

    @property
    def base(self):
        """Base of the tuple."""
        return self.types[:-1] if self.has_varargs() else self.types

    def has_varargs(self):
        """Check whether this tuple has varargs."""
        return len(self.types) > 0 and isinstance(self.types[-1], VarArgs)

    @property
    def varargs_type(self):
        """Type of the varargs."""
        return self.types[-1].arg_type

    def is_compatible(self, other):
        """Check whether this tuple is compatible with another one."""
        return (len(self) == len(other)
                or (len(self) > len(other) and other.has_varargs())
                or (len(self) < len(other) and self.has_varargs()))
