import logging

from .dispatcher import Dispatcher
from .function import (
    promised_type_of as promised_type_of1,
)
from .type import (
    TypeMeta,
    promised_type_of as promised_type_of2,
    ComparableType,
    Union,
    PromisedList,
    PromisedTuple,
    ptype,
    is_type,
)
from .util import multihash

__all__ = [
    "parametric",
    "type_parameter",
    "kind",
    "Kind",
    "List",
    "Tuple",
    "type_of",
]

log = logging.getLogger(__name__)

_dispatch = Dispatcher()


class ParametricTypeMeta(TypeMeta):
    """Parametric types can be instantiated with indexing.

    A concrete parametric type can be instantiated by calling `Type[Par1, Par2]`.
    If `Type(Arg1, Arg2, **kw_args)` is called, this returns
    `Type[type(Arg1), type(Arg2)](Arg1, Arg2, **kw_args)`.
    """

    def __getitem__(self, p):
        if not self.is_concrete:
            if isinstance(p, tuple):
                return self.__new__(self, *p)
            else:
                return self.__new__(self, p)
        else:
            raise TypeError("Cannot specify type parameters. This type is concrete.")

    def __call__(cls, *args, **kw_args):
        # `Type(arg1, arg2, **kw_args)` will first construct the
        # parametric subtype `T = Type[type(arg1), type(arg2)]`
        # and then call the equivalent of `T(arg1, arg2, **kw_args)`.

        if not cls.is_concrete:
            type_parameter = tuple(type(arg) for arg in args)
            if len(type_parameter) == 1:
                type_parameter = type_parameter[0]
            T = cls[type_parameter]
        else:
            T = cls

        # Calls `__new__` and `__init__`.
        return type.__call__(T, *args, **kw_args)

    @property
    def is_concrete(cls):
        """bool: Check whether the parametric type is instantiated or not."""
        return hasattr(cls, "_is_parametric")


class CovariantMeta(ParametricTypeMeta):
    """A metaclass that implements *covariance* of parametric types."""

    def __subclasscheck__(self, subclass):
        if hasattr(subclass, "_is_parametric"):
            # Check that they are instances of the same parametric type.
            if subclass.__bases__ == self.__bases__:
                par_subclass = type_parameter(subclass)
                par_self = type_parameter(self)

                # Handle the case that the parameters are types.
                if is_type(par_subclass) and is_type(par_self):
                    return ptype(par_subclass) <= ptype(par_self)

                # Handle the case that the parameters are tuples of types.
                if (
                    isinstance(par_subclass, tuple)
                    and isinstance(par_self, tuple)
                    and len(par_subclass) == len(par_self)
                    and all(is_type(pi_subclass) for pi_subclass in par_subclass)
                    and all(is_type(pi_self) for pi_self in par_self)
                ):
                    return all(
                        ptype(pi_subclass) <= ptype(pi_self)
                        for pi_subclass, pi_self in zip(par_subclass, par_self)
                    )

        # Default behaviour to `type`s subclass check.
        return type.__subclasscheck__(self, subclass)


def parametric(Class):
    """A decorator for parametric classes."""
    subclasses = {}

    if not issubclass(Class, object):  # pragma: no cover
        raise RuntimeError(
            f"To let {Class} be a parametric class, it must be a new-style class."
        )

    def __new__(cls, *ps):
        # Only create new subclass if it doesn't exist already.
        if ps not in subclasses:

            def __new__(cls, *args, **kw_args):
                return Class.__new__(cls)

            # Create subclass.
            name = Class.__name__ + "[" + ",".join(str(p) for p in ps) + "]"
            SubClass = type.__new__(
                CovariantMeta,
                name,
                (ParametricClass,),
                {"__new__": __new__, "_is_parametric": True},
            )
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
    ParametricClass = ParametricTypeMeta(Class.__name__, (Class,), {"__new__": __new__})
    ParametricClass.__module__ = Class.__module__

    # Attempt to correct docstring.
    try:
        ParametricClass.__doc__ = Class.__doc__
    except AttributeError:  # pragma: no cover
        pass

    return ParametricClass


@_dispatch
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

    IMPORTANT:
        `List` should not be used to generically refer to a list! Use `list` instead.

    Args:
        el_type (type or ptype): Element type.
    """

    def __init__(self, el_type):
        self._el_type = ptype(el_type)

    def __hash__(self):
        return multihash(List, self._el_type)

    def __repr__(self):
        return f"List[{self._el_type}]"

    def get_types(self):
        return (_ParametricList[self._el_type],)

    @property
    def parametric(self):
        return True


# Deliver `List`.
PromisedList.deliver(List)


@parametric
class _ParametricTuple(tuple):
    """Parametric tuple type."""


class Tuple(ComparableType):
    """Parametric tuple Plum type.

    IMPORTANT:
        `Tuple` should not be used to generically refer to a tuple! Use `tuple` instead.

    Args:
        *el_types (type or ptype): Element types.
    """

    def __init__(self, *el_types):
        self._el_types = tuple(ptype(el_type) for el_type in el_types)

    def __hash__(self):
        return multihash(Tuple, *self._el_types)

    def __repr__(self):
        return f'Tuple[{", ".join(map(str, self._el_types))}]'

    def get_types(self):
        return (_ParametricTuple[self._el_types],)

    @property
    def parametric(self):
        return True


# Deliver `Tuple`.
PromisedTuple.deliver(Tuple)


def _types_of_iterable(xs):
    types = {type_of(x) for x in xs}
    if len(types) == 1:
        return list(types)[0]
    else:
        return Union(*types)


@_dispatch
def type_of(obj):
    """Get the Plum type of an object.

    Args:
        obj (object): Object to get type of.

    Returns
        ptype: Plum type of `obj`.
    """
    return ptype(type(obj))


@_dispatch
def type_of(obj: list):
    return List(_types_of_iterable(obj))


@_dispatch
def type_of(obj: tuple):
    return Tuple(*(type_of(x) for x in obj))


# Deliver `type_of`.
promised_type_of1.deliver(type_of)
promised_type_of2.deliver(type_of)
