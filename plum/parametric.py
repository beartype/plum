import logging
from functools import partial

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
    PromisedDict,
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
    "Dict",
    "type_of",
    "Val",
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
        if not self.concrete:
            # `p` can be a tuple, in which case it must be splatted.
            return self.__new__(self, *(p if isinstance(p, tuple) else (p,)))
        else:
            raise TypeError("Cannot specify type parameters. This type is concrete.")

    def __call__(cls, *args, **kw_args):
        # `Type(arg1, arg2, **kw_args)` will first construct the
        # parametric subtype `T = Type[type(arg1), type(arg2)]`
        # and then call the equivalent of `T(arg1, arg2, **kw_args)`.

        if hasattr(cls, "parametric") and cls.parametric:
            if not cls.concrete:
                type_parameter = cls.__infer_type_parameter__(*args, **kw_args)
                cls = cls[type_parameter]

        # Calls `__new__` and `__init__`.
        return TypeMeta.__call__(cls, *args, **kw_args)

    def __infer_type_parameter__(cls, *args, **kw_args):
        """Function called when the constructor of this parametric type is called
        before the parameters have been specified.

        The default behaviour is to take as parameters the type of every argument,
        but this behaviour can be overridden by redefining this function on the
        metaclass.

        Args:
            *args: Positional arguments passed to the `__init__` method.
            *kw_args: Keyword arguments passed to the `__init__` method.

        Returns:
            type or tuple[type]: A type or tuple of types.
        """
        # TODO: Use `type_of` instead of `type`.
        type_parameter = tuple(type(arg) for arg in args)
        if len(type_parameter) == 1:
            type_parameter = type_parameter[0]
        return type_parameter

    @property
    def parametric(cls):
        """bool: Check whether the type is a parametric type."""
        return hasattr(cls, "_parametric") and cls._parametric

    @property
    def concrete(cls):
        """bool: Check whether the parametric type is instantiated or not."""
        if cls.parametric:
            return hasattr(cls, "_concrete") and cls._concrete
        else:
            raise RuntimeError(
                "Cannot check whether a non-parametric type is instantiated or not."
            )

    @property
    def type_parameter(cls):
        """object: Get the type parameter. Parametric type must be instantiated."""
        if cls.concrete:
            return cls._type_parameter
        else:
            raise RuntimeError(
                "Cannot get the type parameter of non-instantiated parametric type."
            )

    @property
    def runtime_type_of(cls):
        """bool: Check whether the type requires :func:`.parametric.type_of` at
        runtime"""
        return hasattr(cls, "_runtime_type_of") and cls._runtime_type_of


class CovariantMeta(ParametricTypeMeta):
    """A metaclass that implements *covariance* of parametric types."""

    def __subclasscheck__(self, subclass):
        if (
            self.parametric
            and (hasattr(subclass, "parametric") and subclass.parametric)
            and self.concrete
            and subclass.concrete
        ):
            # Check that they are instances of the same parametric type.
            if all(issubclass(b, self.__bases__) for b in subclass.__bases__):
                par_subclass = subclass.type_parameter
                par_self = self.type_parameter

                # Handle the case that the parameters are types.
                if is_type(par_subclass) and is_type(par_self):
                    return ptype(par_subclass) <= ptype(par_self)

                if not isinstance(par_subclass, tuple):
                    par_subclass = (par_subclass,)
                if not isinstance(par_self, tuple):
                    par_self = (par_self,)

                # Handle the case that the parameters are tuples of types.
                if len(par_subclass) == len(par_self):
                    return all(
                        (
                            # Type parameter could be a type.
                            ptype(pi_subclass) <= ptype(pi_self)
                            if (is_type(pi_subclass) or is_type(pi_self))
                            # Type parameter could also be an object.
                            else pi_subclass == pi_self
                        )
                        for pi_subclass, pi_self in zip(par_subclass, par_self)
                    )

        # Default behaviour to `type`s subclass check.
        return type.__subclasscheck__(self, subclass)


def parametric(Class=None, runtime_type_of=False):
    """A decorator for parametric classes.

    When the constructor of this parametric type is called before the type parameter
    has been specified, the type parameters are inferred from the arguments of the
    constructor by calling the following function.

    The default implementation is shown here, but it is possible to override it.

    ```python
    @classmethod
    def __infer_type_parameter__(cls, *args, **kw_args) -> Tuple:
        return tuple(type(arg) for arg in args)
    ```
    """

    # Allow the keyword arguments to be passed in without using `functools.partial`
    # explicitly.
    if Class is None:
        return partial(parametric, runtime_type_of=runtime_type_of)

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
            name = Class.__name__ + "[" + ", ".join(str(p) for p in ps) + "]"
            SubClass = type.__new__(
                CovariantMeta,
                name,
                (ParametricClass,),
                {"__new__": __new__},
            )
            SubClass._parametric = True
            SubClass._concrete = True
            SubClass._runtime_type_of = runtime_type_of
            SubClass._type_parameter = ps[0] if len(ps) == 1 else ps
            SubClass.__module__ = Class.__module__

            # Attempt to correct docstring.
            try:
                SubClass.__doc__ = Class.__doc__
            except AttributeError:  # pragma: no cover
                pass

            subclasses[ps] = SubClass
        return subclasses[ps]

    def __init_subclass__(cls, **kw_args):
        cls._parametric = False
        cls._runtime_type_of = False
        if cls.__new__ is __new__:

            def resetted_new(cls, *args, **kw_args):
                return Class.__new__(cls)

            cls.__new__ = resetted_new
        Class.__init_subclass__(**kw_args)

    # Create parametric class.
    ParametricClass = ParametricTypeMeta(
        Class.__name__,
        (Class,),
        {"__new__": __new__, "__init_subclass__": __init_subclass__},
    )
    ParametricClass._parametric = True
    ParametricClass._concrete = False
    ParametricClass._runtime_type_of = runtime_type_of
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
    return type(x).type_parameter


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

    @property
    def runtime_type_of(self):
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

    @property
    def runtime_type_of(self):
        return True


# Deliver `Tuple`.
PromisedTuple.deliver(Tuple)


@parametric
class _ParametricDict(dict):
    """Parametric dictionary type."""


class Dict(ComparableType):
    """Parametric dictionary Plum type.

    IMPORTANT:
        `Dict` should not be used to generically refer to a dictionary! Use `dict` instead.

    Args:
        key_type (type or ptype): Type of the keys.
        value_type (type or ptype): Type of the values.
    """

    def __init__(self, key_type, value_type):
        self._key_type = ptype(key_type)
        self._value_type = ptype(value_type)

    def __hash__(self):
        return multihash(Dict, self._key_type, self._value_type)

    def __repr__(self):
        return f"Dict[{self._key_type}, {self._value_type}]"

    def get_types(self):
        return (_ParametricDict[self._key_type, self._value_type],)

    @property
    def parametric(self):
        return True

    @property
    def runtime_type_of(self):
        return True


# Deliver `Dict`.
PromisedDict.deliver(Dict)


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


@_dispatch
def type_of(obj: dict):
    return Dict(_types_of_iterable(obj.keys()), _types_of_iterable(obj.values()))


# Deliver `type_of`.
promised_type_of1.deliver(type_of)
promised_type_of2.deliver(type_of)


@parametric
class Val:
    """A parametric type used to move information from the value domain to the type
    domain.
    """

    @classmethod
    def __infer_type_parameter__(cls, *arg):
        """Function called when the constructor of `Val` is called to determine the type
        parameters.
        """
        if len(arg) == 0:
            raise ValueError("The value must be specified.")
        elif len(arg) > 1:
            raise ValueError("Too many values. `Val` accepts only one argument.")
        return arg[0]

    def __init__(self, val=None):
        """Construct a value object with type `Val(arg)` that can be used to dispatch
        based on values.

        Args:
            val (object): The value to be moved to the type domain.
        """
        if type(self).concrete:
            if val is not None and type_parameter(self) != val:
                raise ValueError("The value must be equal to the type parameter.")
        else:
            raise ValueError("The value must be specified.")

    def __repr__(self):
        return f"{repr(ptype(type(self)))}()"

    def __eq__(self, other):
        return type(self) == type(other)
