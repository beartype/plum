from functools import partial

from beartype.door import TypeHint
from beartype.roar import BeartypeDoorNonpepException

from .dispatcher import Dispatcher
from .type import resolve_type_hint
from .util import repr_short

__all__ = [
    "parametric",
    "type_parameter",
    "kind",
    "Kind",
    "Val",
]


_dispatch = Dispatcher()


class ParametricTypeMeta(type):
    """Parametric types can be instantiated with indexing.

    A concrete parametric type can be instantiated by calling `Type[Par1, Par2]`.
    If `Type(Arg1, Arg2, **kw_args)` is called, this returns
    `Type[type(Arg1), type(Arg2)](Arg1, Arg2, **kw_args)`.
    """

    def __getitem__(cls, p):
        if not cls.concrete:
            # `p` can be a tuple, in which case it must be splatted.
            return cls.__new__(cls, *(p if isinstance(p, tuple) else (p,)))
        else:
            raise TypeError("Cannot specify type parameters. This type is concrete.")

    def __call__(cls, *args, **kw_args):
        # `Type(arg1, arg2, **kw_args)` will first construct the parametric subtype
        # `T = Type[type(arg1), type(arg2)]` and then call the equivalent of
        # `T(arg1, arg2, **kw_args)`.

        if hasattr(cls, "parametric") and cls.parametric:
            if not cls.concrete:
                type_parameter = cls.__infer_type_parameter__(*args, **kw_args)
                cls = cls[type_parameter]

        # Calls `__new__` and `__init__`.
        return type.__call__(cls, *args, **kw_args)

    def __infer_type_parameter__(cls, *args, **kw_args):
        """Function called when the constructor of this parametric type is called
        before the parameters have been specified.

        The default behaviour is to take as parameters the type of every argument,
        but this behaviour can be overridden by redefining this function on the
        metaclass.

        Args:
            *args: Positional arguments passed to the `__init__` method.
            **kw_args: Keyword arguments passed to the `__init__` method.

        Returns:
            type or tuple[type]: A type or tuple of types.
        """
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


class CovariantMeta(ParametricTypeMeta):
    """A metaclass that implements *covariance* of parametric types."""

    def __subclasscheck__(cls, subclass):
        if is_concrete(cls) and is_concrete(subclass):
            # Check that they are instances of the same parametric type.
            if all(issubclass(b, cls.__bases__) for b in subclass.__bases__):
                par_subclass = subclass.type_parameter
                par_cls = cls.type_parameter

                # Ensure that both are in tuple form.
                if not isinstance(par_subclass, tuple):
                    par_subclass = (par_subclass,)
                if not isinstance(par_cls, tuple):
                    par_cls = (par_cls,)

                return cls._is_sub_type_parameter(par_cls, subclass, par_subclass)

        # Default behaviour to `type`s subclass check.
        return type.__subclasscheck__(cls, subclass)

    def _is_sub_type_parameter(cls, par_cls, subclass, par_subclass):
        # Handle the case that the parameters are tuples of types.
        return len(par_subclass) == len(par_cls) and all(
            (
                # Type parameter could be a type.
                TypeHint(resolve_type_hint(pi_subclass))
                <= TypeHint(resolve_type_hint(pi_self))
                if (is_type(pi_subclass) and is_type(pi_self))
                # Type parameter could also be an object.
                else pi_subclass == pi_self
            )
            for pi_subclass, pi_self in zip(par_subclass, par_cls)
        )


def parametric(Class=None, metaclass=CovariantMeta):
    """A decorator for parametric classes.

    When the constructor of this parametric type is called before the type parameter
    has been specified, the type parameters are inferred from the arguments of the
    constructor by calling the following function.

    The default implementation is shown here, but it is possible to override it.::

        @classmethod
        def __infer_type_parameter__(cls, *args, **kw_args) -> Tuple:
            return tuple(type(arg) for arg in args)

    Args:
        metaclass (type, optional): Metaclass of the parametric class. Defaults to
            :class:`.parametric.CovariantMeta`.
    """

    # Allow the keyword arguments to be passed in without using `functools.partial`
    # explicitly.
    if Class is None:
        return partial(parametric, metaclass=metaclass)

    subclasses = {}

    if not issubclass(Class, object):  # pragma: no cover
        raise RuntimeError(
            f"To let {Class} be a parametric class, it must be a new-style class."
        )

    def __new__(cls, *ps):
        # Only create a new subclass if it doesn't exist already.
        if ps not in subclasses:

            def __new__(cls, *args, **kw_args):
                return Class.__new__(cls)

            # Create subclass.
            name = Class.__name__ + "[" + ", ".join(str(p) for p in ps) + "]"
            SubClass = type.__new__(
                metaclass,
                name,
                (ParametricClass,),
                {"__new__": __new__},
            )
            SubClass._parametric = True
            SubClass._concrete = True
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
        if cls.__new__ is __new__:

            def class_new(cls, *args, **kw_args):
                return Class.__new__(cls)

            cls.__new__ = class_new
        Class.__init_subclass__(**kw_args)

    # Create parametric class.
    ParametricClass = metaclass(
        Class.__name__,
        (Class,),
        {"__new__": __new__, "__init_subclass__": __init_subclass__},
    )
    ParametricClass._parametric = True
    ParametricClass._concrete = False
    ParametricClass.__module__ = Class.__module__

    # Attempt to correct docstring.
    try:
        ParametricClass.__doc__ = Class.__doc__
    except AttributeError:  # pragma: no cover
        pass

    return ParametricClass


def is_concrete(t):
    """Check if a type `t` is a concrete instance of a parametric type.

    Args:
        t (type): Type to check.

    Returns:
        bool: `True` if `t` is a concrete instance of a parametric type and `False`
            otherwise.
    """
    return hasattr(t, "parametric") and t.parametric and t.concrete


def is_type(x):
    """Check whether `x` is a type or a type hint.

    Under the hood, this attempts to construct a :class:`beartype.door.TypeHint` from
    `x`. If successful, then `x` is deemed a type or type hint.

    Args:
        x (object): Object to check.

    Returns:
        bool: Whether `x` is a type or a type hint.
    """
    try:
        TypeHint(x)
        return True
    except BeartypeDoorNonpepException:
        return False


def type_parameter(x):
    """Get the type parameter of concrete parametric type or an instance of a concrete
    parametric type.

    Args:
        x (object): Concrete parametric type or instance thereof.

    Returns:
        object: Type parameter.
    """
    if is_type(x):
        t = x
    else:
        t = type(x)
    if hasattr(t, "parametric"):
        return t.type_parameter
    raise ValueError(
        f"`{x}` is not a concrete parametric type or an instance of a"
        f" concrete parametric type."
    )


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
class Val:
    """A parametric type used to move information from the value domain to the type
    domain."""

    @classmethod
    def __infer_type_parameter__(cls, *arg):
        """Function called when the constructor of `Val` is called to determine the type
        parameters."""
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
        return repr_short(type(self)) + "()"

    def __eq__(self, other):
        return type(self) == type(other)
