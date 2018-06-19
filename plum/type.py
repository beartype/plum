# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, division

import abc

from .resolvable import Reference, Promise
from .util import multihash, Comparable

__all__ = ['VarArgs', 'Union', 'Self', 'PromisedType', 'as_type']


class AbstractType(object):
    """An abstract class defining the top of the type hierarchy."""""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __hash__(self):
        pass

    @abc.abstractmethod
    def __repr__(self):
        pass


class VarArgs(AbstractType):
    """Type that represents a variable number of the same type.

    Args:
        type (type, optional): Type of the variable number of types. Defaults
            to `object`.
    """

    def __init__(self, type=object):
        self.type = as_type(type)

    def __hash__(self):
        return multihash(VarArgs, self.type)

    def __repr__(self):
        return 'VarArgs({})'.format(repr(self.type))

    def expand(self, num):
        """Expand the varargs to a tuple of types.

        Args:
            num (int): Length of the tuple.

        Returns:
            tuple: Expansion.
        """
        return (self.type,) * num


class ComparableType(AbstractType, Comparable):
    """A type that can be compared to other types."""

    def __le__(self, other):
        return issubclass(self, other)

    def __subclasscheck__(self, subclass):
        return all([issubclass(t, self.get_types())
                    for t in subclass.get_types()])

    def __instancecheck__(self, instance):
        return isinstance(instance, self.get_types())

    @abc.abstractmethod
    def get_types(self):
        """Get the types encapsulated by this type.

        Returns:
            tuple[type]: Types encapsulated.
        """
        pass

    def mro(self):
        types = self.get_types()
        if len(types) != 1:
            raise RuntimeError('Exactly one type must be encapsulated to get '
                               'the MRO.')
        return types[0].mro()


class Union(ComparableType):
    """A union of types.

    Args:
        *types (type): Types to encapsulate.
    """

    def __init__(self, *types):
        self._types = tuple(as_type(t) for t in types)

    def __hash__(self):
        return multihash(Union, frozenset(self._types))

    def __repr__(self):
        return '{{{}}}'.format(', '.join(repr(t) for t in self._types))

    def get_types(self):
        return sum([t.get_types() for t in self._types], ())


class Type(ComparableType):
    """A single type.

    Args:
        type (type): Type to encapsulate.
    """

    def __init__(self, type):
        self._type = type

    def __hash__(self):
        return multihash(Type, self._type)

    def __repr__(self):
        if isinstance(self._type, AbstractType):
            return repr(self._type)
        else:
            return '{}.{}'.format(self._type.__module__, self._type.__name__)

    def get_types(self):
        return self._type,


class PromisedType(ComparableType, Promise):
    """A promised type."""

    def __hash__(self):
        return hash(as_type(self.resolve()))

    def __repr__(self):
        return repr(self.resolve())

    def get_types(self):
        return as_type(self.resolve()).get_types()


class Self(Reference, PromisedType):
    """Reference type.

    Note:
        Both :class:`.resolvable.Reference` and :class:`.type.PromisedType`
        implement `resolve()`. We need that from :class:`.resolvable.Reference`,
        so we inherit from :class:`.resolvable.Reference` first.
    """


def as_type(obj):
    """Convert object to a type.

    Args:
        obj (object): Object to convert to type.

    Returns:
        :class:`.type.AbstractType`: Type corresponding to `obj`.
    """
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
        elif len(obj) == 1:
            return VarArgs(as_type(obj[0]))
        else:
            # `len(obj) == 0`.
            return VarArgs()

    # A set is used as shorthand notation for a union.
    if isinstance(obj, set):
        return Union(*obj)

    # Finally, perform conversions if necessary.
    if isinstance(obj, AbstractType):
        return obj
    elif isinstance(type(obj), type):
        return Type(obj)
    else:
        raise RuntimeError('Could not convert "{}" to a type.'.format(obj))
