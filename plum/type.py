# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, division

import abc

from .resolvable import Reference, Promise
from .util import multihash, Comparable

__all__ = ['AbstractType', 'Type', 'Union', 'VarArgs', 'as_type', 'Self',
           'PromisedType']


class AbstractType(object):
    """An abstract class defining the type hierarchy."""""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __hash__(self):
        pass

    @abc.abstractmethod
    def __repr__(self):
        pass


class Union(AbstractType, Comparable):
    """A union of types."""

    def __init__(self, *types):
        self._types = set(types)

    @property
    def types(self):
        return self._types

    def __repr__(self):
        return '{{{}}}'.format(', '.join([t.__name__ for t in self.types]))

    def __hash__(self):
        return multihash(Union, frozenset(self.types))

    def __le__(self, other):
        return all([any([issubclass(x, y) for y in other.types])
                    for x in self.types])


class Type(Union):
    """A type."""

    def __repr__(self):
        return list(self.types)[0].__name__

    def mro(self):
        return list(self.types)[0].mro()


class VarArgs(AbstractType):
    """Type that represents a variable number of types.

    Args:
        type (type, optional): Supertype of all the arguments. Defaults to
            `object`.
    """

    def __init__(self, arg_type=object):
        self.arg_type = as_type(arg_type)

    def __hash__(self):
        return multihash(VarArgs, self.arg_type)

    def __repr__(self):
        return 'VarArgs({})'.format(repr(self.arg_type))

    def expand(self, num):
        """Expand the varargs to a tuple of types.

        Args:
            num (int): Length of the tuple.
        """
        return tuple([self.arg_type] * num)


def as_type(obj):
    """Ensure that an object is a type."""
    # :class:`.type.Self` has a shorthand notation that doesn't require the
    # user to instantiate it.
    if obj is Self:
        return obj()

    # A list is used as shorthand notation for varargs.
    if isinstance(obj, list):
        if len(obj) > 1:
            raise TypeError('Invalid type specification: "{}". Varargs has to '
                            'be specified in one of the following ways: [], '
                            '[Type], VarArgs(), or VarArgs(Type).'
                            ''.format(str(obj)))
        return VarArgs(*map(as_type, obj))

    # A list is used as shorthand notation for a union.
    if isinstance(obj, set):
        return Union(*obj)

    # Finally, perform conversions if necessary.
    if isinstance(obj, AbstractType):
        return obj
    elif isinstance(type(obj), type):
        return Type(obj)
    else:
        raise RuntimeError('Could not convert "{}" to a type.'.format(obj))


class Self(Type, Reference):
    def __init__(self, *types):
        Type.__init__(self, *types)
        Reference.__init__(self)

    @property
    def types(self):
        return {self.resolve()}


class PromisedType(Type, Promise):
    def __init__(self, *types):
        Type.__init__(self, *types)
        Promise.__init__(self)

    @property
    def types(self):
        obj = self.resolve()
        if type(obj) == type:
            return {obj}
        elif type(obj) == set:
            return obj
        else:
            raise RuntimeError('Unknown resolved object "{}".'.format(obj))
