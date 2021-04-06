import logging

from .dispatcher import Dispatcher
from .function import promised_convert
from .parametric import type_of
from .type import ptype, TypeType

__all__ = [
    "convert",
    "add_conversion_method",
    "conversion_method",
    "add_promotion_rule",
    "promote",
]

log = logging.getLogger(__name__)

_dispatch = Dispatcher()


@_dispatch
def convert(obj, type_to: TypeType):
    """Convert an object to a particular type.

    Args:
        obj (object): Object to convert.
        type_to (type): Type to convert to.

    Returns:
        object: `obj` converted to type `type_to`.
    """
    return _convert.invoke(type_of(obj), type_to)(obj, type_to)


# Deliver `convert`.
promised_convert.deliver(convert)


@_dispatch
def _convert(obj, type_to):
    type_from = type_of(obj)
    type_to = ptype(type_to)
    if type_from <= type_to:
        return obj
    else:
        raise TypeError(f'Cannot convert a "{type_from}" to a "{type_to}".')


def add_conversion_method(type_from, type_to, f):
    """Add a conversion method to convert an object from one type to another.

    Args:
        type_from (type): Type to convert from.
        type_to (type): Type to convert to.
        f (function): Function that converts an object of type `type_from` to
            type `type_to`.
    """

    @_convert.dispatch
    def perform_conversion(obj: type_from, _: type_to):
        return f(obj)


def conversion_method(type_from, type_to):
    """Decorator to add a conversion method to convert an object from one
    type to another.

    Args:
        type_from (type): Type to convert from.
        type_to (type): Type to convert to.
    """

    def add_method(f):
        add_conversion_method(type_from, type_to, f)

    return add_method


# Add some common conversion methods.
add_conversion_method(object, tuple, lambda x: (x,))
add_conversion_method(tuple, tuple, lambda x: x)
add_conversion_method(list, tuple, tuple)
add_conversion_method(object, list, lambda x: (x,))
add_conversion_method(list, list, lambda x: x)
add_conversion_method(tuple, list, list)
add_conversion_method(bytes, str, lambda x: x.decode("utf-8", "replace"))


@_dispatch
def _promotion_rule(type1, type2):
    """Promotion rule.

    Args:
        type1 (ptype): First type to promote.
        type2 (ptype): Second type to promote.

    Returns:
        type: Type to convert to.
    """
    type1 = ptype(type1)
    type2 = ptype(type2)
    if type1 <= type2:
        return type2
    elif type2 <= type1:
        return type1
    else:
        raise TypeError(f'No promotion rule for "{type1}" and "{type2}".')


@_dispatch
def add_promotion_rule(type1, type2, type_to):
    """Add a promotion rule.

    Args:
        type1 (type): First type to promote.
        type2 (type): Second type to promote.
        type_to (type): Type to convert to.
    """

    @_promotion_rule.dispatch
    def rule(t1: type1, t2: type2):
        return type_to

    if ptype(type1) != ptype(type2):

        @_promotion_rule.dispatch
        def rule(t1: type2, t2: type1):
            return type_to


@_dispatch
def promote(obj1, obj2, *objs):
    """Promote objects to a common type.

    Args:
        *objs (object): Objects to convert.

    Returns:
        tuple: `objs`, but all converted to a common type.
    """
    # Convert to a single tuple.
    objs = (obj1, obj2) + objs

    # Get the types of the objects.
    types = [type_of(obj) for obj in objs]

    # Find the common type.
    common_type = _promotion_rule.invoke(types[0], types[1])(types[0], types[1])
    for i, t in enumerate(types[2:]):
        common_type = _promotion_rule.invoke(common_type, t)(common_type, t)

    # Convert objects and return.
    return tuple(convert(obj, ptype(common_type)) for obj in objs)


@_dispatch
def promote(obj):
    # Promote should always return a tuple to avoid edge cases.
    return (obj,)


@_dispatch()
def promote():
    return ()
