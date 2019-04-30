# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, division

import abc
import logging
from itertools import combinations

from .resolvable import Reference, Promise
from .util import multihash, Comparable

__all__ = ['VarArgs',
           'Union',
           'Type',
           'PromisedType',
           'Self',
           'TypeType',
           'as_type',
           'is_object',
           'is_type']
log = logging.getLogger(__name__)


class AbstractType(object):
    """An abstract class defining the top of the Plum type hierarchy.

    Any instance of a subclass of :class:`.type.AbstractType` will be henceforth
    referred to be of type Plum type or `ptype`.
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __hash__(self):
        pass  # pragma: no cover

    @abc.abstractmethod
    def __repr__(self):
        pass  # pragma: no cover

    @property
    def parametric(self):
        """Boolean that indicates whether this is or contains a parametric
        type."""
        return False


class VarArgs(AbstractType):
    """Plum type that represents a variable number of the same Plum type.

    Args:
        type (type or ptype, optional): Type or Plum type of the variable
            number of types. Defaults to `object`.
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

    @property
    def parametric(self):
        return self.type.parametric


class ComparableType(AbstractType, Comparable):
    """A Plum type that can be compared to other Plum types."""

    def __le__(self, other):
        return issubclass(self, other)

    def __subclasscheck__(self, subclass):
        return all([issubclass(t, self.get_types())
                    for t in subclass.get_types()])

    def __instancecheck__(self, instance):
        return isinstance(instance, self.get_types())

    @abc.abstractmethod
    def get_types(self):
        """Get the types encapsulated by this Plum type.

        Returns:
            tuple[type]: Types encapsulated.
        """

    def mro(self):
        types = self.get_types()
        if len(types) != 1:
            raise RuntimeError('Exactly one type must be encapsulated to get '
                               'the MRO.')
        return types[0].mro()


class Union(ComparableType):
    """A union of Plum types.

    Args:
        *types (type or ptype): Types or Plum types to encapsulate.
    """

    def __init__(self, *types):
        # Lazily convert to a set to avoid resolution errors.
        self._types = tuple(as_type(t) for t in types)

    def _to_set(self):
        self._types = set(self._types)

    def __hash__(self):
        self._to_set()
        if len(self._types) == 1:
            return hash(list(self._types)[0])
        else:
            return multihash(Union, frozenset(self._types))

    def __repr__(self):
        self._to_set()
        if len(self._types) == 1:
            return repr(list(self._types)[0])
        else:
            return '{{{}}}'.format(', '.join(repr(t) for t in self._types))

    def get_types(self):
        self._to_set()
        return sum([t.get_types() for t in self._types], ())

    @property
    def parametric(self):
        self._to_set()
        return any(t.parametric for t in self._types)

    def expand(self, parametric_type=lambda x: x):
        self._to_set()
        result = set()
        for num in range(1, len(self._types) + 1):
            result |= set(Union(*xs) for xs in combinations(self._types, num))
        return Union(*[parametric_type(x) for x in result])


class Type(ComparableType):
    """A Plum type encapsulating a single type.

    Args:
        type (type): Type to encapsulate.
    """

    def __init__(self, type):
        self._type = type

    def __hash__(self):
        return multihash(Type, self._type)

    def __repr__(self):
        return '{}.{}'.format(self._type.__module__, self._type.__name__)

    def get_types(self):
        return self._type,


class PromisedType(ComparableType, Promise):
    """A promised Plum type."""

    def __hash__(self):
        return hash(as_type(self.resolve()))

    def __repr__(self):
        return repr(self.resolve())

    def get_types(self):
        return as_type(self.resolve()).get_types()

    @property
    def parametric(self):
        return as_type(self.resolve()).parametric


class Self(Reference, PromisedType):
    """Reference Plum type.

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
        :class:`.type.AbstractType`: Plum type corresponding to `obj`.
    """
    # If `obj` is already a Plum type, we're done.
    if isinstance(obj, AbstractType):
        return obj

    # A list is used as shorthand notation for varargs.
    if isinstance(obj, list):
        if len(obj) > 1:
            raise TypeError('Invalid type specification: "{}". Varargs has to '
                            'be specified in one of the following ways: [], '
                            '[Type], VarArgs(), or VarArgs(Type).'
                            ''.format(str(obj)))
        elif len(obj) == 1:
            return VarArgs(as_type(obj[0]))
        else:  # `len(obj) == 0`.
            return VarArgs()

    # A set is used as shorthand notation for a union.
    if isinstance(obj, set):
        return Union(*obj)

    # If `obj` is a `type`, handle shorthands; otherwise, wrap it in `Type`.
    if isinstance(obj, type):
        # :class:`.type.Self` has a shorthand notation that doesn't require the
        # user to instantiate it.
        if obj is Self:
            return obj()

        return Type(obj)

    raise RuntimeError('Could not convert "{}" to a type.'.format(obj))


def is_object(t):
    """A fast comparison to check if a Plum type is `object`.

    Args:
        t (ptype): Type to check.

    Returns:
        bool: `t` is `object`.
    """
    return t.get_types() == (object,)


def is_type(t):
    """Fast check for whether an object is a type.

    Args:
        t (object): Object to check.

    Returns:
        bool: `t` is `object`.
    """
    return isinstance(t, TypeType.get_types())


TypeType = Union(type, AbstractType, list, set)
"""The type of a Plum type, including shorthands."""
