# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import logging

from .dispatcher import Dispatcher
from .type import ComparableType, as_type, TypeType, \
    promised_type_of as promised_type_of2, is_type
from .util import multihash
from .function import promised_type_of as promised_type_of1

__all__ = ['parametric',
           'type_parameter',
           'kind',
           'Kind',
           'List',
           'Tuple',
           'type_of']
log = logging.getLogger(__name__)

_dispatch = Dispatcher()


@_dispatch(object)
def _get_id(x):
    return id(x)


@_dispatch({int, float, str, TypeType})
def _get_id(x):
    return x


class CovariantType(type):
    """A metaclass that implements *covariance* of parametric types."""
    def __subclasscheck__(self, subclass):
        if hasattr(subclass, '_is_parametric'):
            # Check that they are instances of the same parametric type.
            if subclass.__bases__ == self.__bases__:
                par_subclass = type_parameter(subclass)
                par_self = type_parameter(self)
                # Check that the type parameters are types.
                if is_type(par_subclass) and is_type(par_self):
                    return as_type(par_subclass) <= as_type(par_self)

        # Default behaviour to `type`s subclass check.
        return type.__subclasscheck__(self, subclass)


def parametric(Class):
    """A decorator for parametric classes."""
    subclasses = {}

    if not issubclass(Class, object):  # pragma: no cover
        raise RuntimeError('To let {} be a parametric class, it must be a '
                           'new-style class.')

    def __new__(cls, *ps):
        # Convert type parameters.
        ps = tuple(_get_id(p) for p in ps)

        # Only create new subclass if it doesn't exist already.
        if ps not in subclasses:
            def __new__(cls, *args, **kw_args):
                return Class.__new__(cls)

            # Create subclass.
            name = Class.__name__ + '{' + ','.join(str(p) for p in ps) + '}'
            SubClass = type.__new__(CovariantType,
                                    name,
                                    (ParametricClass,),
                                    {'__new__': __new__,
                                     '_is_parametric': True})
            SubClass._type_parameter = ps[0] if len(ps) == 1 else ps
            SubClass.__module__ = Class.__module__

            # Attempt to correct docstring.
            try:
                SubClass.__doc__ = Class.__doc__
            except AttributeError:  # pragma: no cover
                pass

            subclasses[ps] = SubClass
        return subclasses[ps]

    # Create parametric class.
    ParametricClass = type(Class.__name__,
                           (Class,),
                           {'__new__': __new__})
    ParametricClass.__module__ = Class.__module__

    # Attempt to correct docstring.
    try:
        ParametricClass.__doc__ = Class.__doc__
    except AttributeError:  # pragma: no cover
        pass

    return ParametricClass


@_dispatch(object)
def type_parameter(x):
    """Get the type parameter of an instance of a parametric type.

    Args:
        x (object): Instance of a parametric type.

    Returns:
        object: Type parameter.
    """
    return x._type_parameter


def kind(SuperClass=object):
    """Create a parametric wrapper type for dispatch purposes.

    Args:
        SuperClass (type): Super class.

    Returns:
        object: New parametric type wrapper.
    """

    @parametric
    class Kind(SuperClass):
        def __init__(self, *xs):
            self.xs = xs

        def get(self):
            return self.xs[0] if len(self.xs) == 1 else self.xs

    return Kind


Kind = kind()  #: A default kind provided for convenience.


@parametric
class _ParametricList(list):
    """Parametric list type."""


class List(ComparableType):
    """Parametric list Plum type.

    Args:
        el_type (type or ptype): Element type.
    """

    def __init__(self, el_type):
        self._el_type = as_type(el_type)

    def __hash__(self):
        return multihash(List, self._el_type)

    def __repr__(self):
        return 'ListType({})'.format(self._el_type)

    def get_types(self):
        return _ParametricList(self._el_type),

    @property
    def parametric(self):
        return True


@parametric
class _ParametricTuple(tuple):
    """Parametric tuple type."""


class Tuple(ComparableType):
    """Parametric tuple Plum type.

    Args:
        el_type (type or ptype): Element type.
    """

    def __init__(self, el_type):
        self._el_type = as_type(el_type)

    def __hash__(self):
        return multihash(Tuple, self._el_type)

    def __repr__(self):
        return 'TupleType({})'.format(self._el_type)

    def get_types(self):
        return _ParametricTuple(self._el_type),

    @property
    def parametric(self):
        return True


def _types_of_iterable(xs):
    types = {type_of(x) for x in xs}
    if len(types) == 1:
        return list(types)[0]
    else:
        return as_type(types)


def type_of(obj):
    """Get the Plum type of an object.

    Args:
        obj (object): Object to get type of.

    Returns
        ptype: Plum type of `obj`.
    """
    if isinstance(obj, list):
        return List(_types_of_iterable(obj))

    if isinstance(obj, tuple):
        return Tuple(_types_of_iterable(obj))

    return as_type(type(obj))


# Deliver `type_of`.
promised_type_of1.deliver(type_of)
promised_type_of2.deliver(type_of)
