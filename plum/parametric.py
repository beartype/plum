import contextlib
from typing import Type, TypeVar, Union

import beartype.door
from beartype.roar import BeartypeDoorNonpepException

from .dispatcher import Dispatcher
from .function import _owner_transfer
from .repr import repr_short
from .type import resolve_type_hint
from .util import TypeHint

__all__ = [
    "CovariantMeta",
    "parametric",
    "type_parameter",
    "type_nonparametric",
    "type_unparametrized",
    "kind",
    "Kind",
    "Val",
]

T = TypeVar("T")


_dispatch = Dispatcher()


class ParametricTypeMeta(type):
    """Parametric types can be instantiated with indexing.

    A concrete parametric type can be instantiated by calling `Type[Par1, Par2]`.
    If `Type(Arg1, Arg2, **kw_args)` is called, this returns
    `Type[type(Arg1), type(Arg2)](Arg1, Arg2, **kw_args)`.
    """

    def __getitem__(cls, p):
        if not cls.concrete:
            # Initialise the type parameters. This can perform, e.g., validation.
            p = p if isinstance(p, tuple) else (p,)  # Ensure that it is a tuple.
            p = cls.__init_type_parameter__(*p)
            # Type parameter has been initialised! Proceed to construct the type.
            p = p if isinstance(p, tuple) else (p,)  # Again ensure that it is a tuple.
            return cls.__new__(cls, *p)
        else:
            raise TypeError("Cannot specify type parameters. This type is concrete.")

    def __concrete_class__(cls, *args, **kw_args):
        """If `cls` is not a concrete class, infer the type parameters and return a
        concrete class. If `cls` is already a concrete class, simply return it.

        Args:
            *args: Positional arguments passed to the `__init__` method.
            **kw_args: Keyword arguments passed to the `__init__` method.

        Returns:
            type: A concrete class.
        """
        if getattr(cls, "parametric", False) and not cls.concrete:
            type_parameter = cls.__infer_type_parameter__(*args, **kw_args)
            cls = cls[type_parameter]
        return cls

    def __init_type_parameter__(cls, *ps):
        """Function called to initialise the type parameters.

        The default behaviour is to just return `ps`.

        Args:
            *ps (object): Type parameters.

        Returns:
            object: Initialised type parameters.
        """
        return ps

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
        return getattr(cls, "_parametric", False)

    @property
    def concrete(cls):
        """bool: Check whether the parametric type is instantiated or not."""
        if cls.parametric:
            return getattr(cls, "_concrete", False)
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


def _default_le_type_par(
    p_left: Union[TypeHint, object], p_right: Union[TypeHint, object]
) -> bool:
    if is_type(p_left) and is_type(p_right):
        p_left = beartype.door.TypeHint(resolve_type_hint(p_left))
        p_right = beartype.door.TypeHint(resolve_type_hint(p_right))
        return p_left <= p_right
    else:
        return p_left == p_right


class CovariantMeta(ParametricTypeMeta):
    """A metaclass that implements *covariance* of parametric types."""

    def __subclasscheck__(cls, subclass):
        # Check that they are instances of the same parametric type.
        if (
            is_concrete(cls)
            and is_concrete(subclass)
            and all(issubclass(b, cls.__bases__) for b in subclass.__bases__)
        ):
            p_sub = subclass.type_parameter
            p_cls = cls.type_parameter
            # Ensure that both are in tuple form.
            p_sub = p_sub if isinstance(p_sub, tuple) else (p_sub,)
            p_cls = p_cls if isinstance(p_cls, tuple) else (p_cls,)
            return cls.__le_type_parameter__(p_sub, p_cls)

        # Default behaviour to `type`s subclass check.
        return type.__subclasscheck__(cls, subclass)

    def __instancecheck__(cls, instance):
        # If `A` is a parametric type, then `A[T1]` and `A[T2]` are subclasses of
        # `A`. With the implementation of `__subclasscheck__` above, we have that
        # `issubclass(A[T1], A[T2])` whenever `issubclass(T1, T2)`. _However_,
        # `isinstance(A[T1](), A[T2])` will fall back to `type.__ininstance__`, which
        # will conclude that `A[T1]` is not a subclass of `A[T2]` because it bypasses
        # the above implementation of `__subclasscheck__`. We therefore implement
        # `__instancecheck__` to ensure that `isinstance(A[T1](), A[T2])` whenever
        # `issubclass(T1, T2)`. In any case, we do first try `type.__instancecheck__`,
        # since it is fast and only gives true positives.
        return type.__instancecheck__(cls, instance) or issubclass(type(instance), cls)

    def __le_type_parameter__(cls, p_left, p_right):
        # Check that there are an equal number of parameters.
        if len(p_left) != len(p_right):
            return False
        # Check every pair of parameters.
        return all(_default_le_type_par(p1, p2) for p1, p2 in zip(p_left, p_right))


def parametric(original_class=None):
    """A decorator for parametric classes.

    When the constructor of this parametric type is called before the type parameter
    has been specified, the type parameter is inferred from the arguments of the
    constructor by calling `__inter_type_parameter__`. The default implementation is
    shown here, but it is possible to override it::

        @classmethod
        def __infer_type_parameter__(cls, *args, **kw_args) -> tuple:
            return tuple(type(arg) for arg in args)

    After the type parameter is given or inferred, `__init_type_parameter__` is called.
    Again, the default implementation is show here, but it is possible to override it::

        @classmethod
        def __init_type_parameter__(cls, *ps) -> tuple:
            return ps

    To determine which one instance of a parametric class is a subclass of another,
    the type parameters are compared with `__le_type_parameter__`::

        @classmethod
        def __le_type_parameter__(cls, left, right) -> bool:
            # Is `left <= right`?
            ...

    """

    original_meta = type(original_class)

    # Make a metaclass that derives from both the metaclass of `original_meta` and
    # `CovariantMeta`, but make sure not to insert `CovariantMeta` twice, because that
    # will error.

    if CovariantMeta in original_meta.__mro__:
        bases = (original_meta,)
        name = original_meta.__name__
    else:
        bases = (CovariantMeta, original_meta)
        name = f"CovariantMeta[{repr_short(original_meta)}]"

    def __call__(cls, *args, **kw_args):
        cls = cls.__concrete_class__(*args, **kw_args)
        return original_meta.__call__(cls, *args, **kw_args)

    def __instancecheck__(cls, instance):
        # An implementation of `__instancecheck__` is necessary to ensure that
        # `isinstance(A[SubType](), A[Type])`. `CovariantMeta` comes first in the MRO,
        # but the implementation of `__instancecheck__` should be taken from
        # `original_meta` if it exists. The implementation of `CovariantMeta` should be
        # used as a fallback. Note that `original_meta.__instancecheck__` always exists.
        # We check that it is not equal to the default `type.__instancecheck__`.
        if original_meta.__instancecheck__ != type.__instancecheck__:
            return original_meta.__instancecheck__(cls, instance)
        else:
            return CovariantMeta.__instancecheck__(cls, instance)

    meta = type(
        name,
        bases,
        {
            "__call__": __call__,
            "__instancecheck__": __instancecheck__,
        },
    )

    subclasses = {}

    def __new__(cls, *ps):
        # Only create a new subclass if it doesn't exist already.
        if ps not in subclasses:

            def __new__(cls, *args, **kw_args):
                return original_class.__new__(cls)

            # Create subclass.
            name = original_class.__name__
            name += "[" + ", ".join(repr_short(p) for p in ps) + "]"
            subclass = meta(
                name,
                (parametric_class,),
                {"__new__": __new__},
            )
            subclass._parametric = True
            subclass._concrete = True
            subclass._type_parameter = ps[0] if len(ps) == 1 else ps
            subclass.__module__ = original_class.__module__

            # Attempt to correct docstring.
            with contextlib.suppress(AttributeError):
                subclass.__doc__ = original_class.__doc__

            subclasses[ps] = subclass
        return subclasses[ps]

    def __init_subclass__(cls, **kw_args):
        cls._parametric = False
        # If the subclass has the same `__new__` as `ParametricClass`, then we should
        # replace it with the `__new__` of `Class`. If the user already defined another
        # `__new__`, then everything is fine.
        if cls.__new__ is __new__:

            def class_new(cls, *args, **kw_args):
                return original_class.__new__(cls)

            cls.__new__ = class_new
        super(original_class, cls).__init_subclass__(**kw_args)

    def __class_nonparametric__(cls):
        """Return the non-parametric type of an object.

        :mod:`plum.parametric` produces parametric subtypes of classes. This
        method can be used to get the original non-parametric type of an object.

        See Also
        --------
        :func:`plum.type_nonparametric`
            The more-user-friendly function equivalent of this method.
        :func:`plum.type_unparametrized`
            A function that returns the non-concrete, but still parametric, type
            of an object.

        Examples
        --------
        In this example we will demonstrate how to retrieve the original
        non-parametric class from a :func:`plum.parametric` decorated class.

        :func:`plum.parametric` defines a parametric class of the same name as
        the original class, and then creates a subclass of the original class
        with the type parameter inferred from the arguments of the constructor.

        >>> from plum import parametric
        >>> class Obj:
        ...     @classmethod
        ...     def __infer_type_parameter__(cls, *arg):
        ...         return type(arg[0])
        ...
        ...     def __init__(self, x):
        ...         self.x = x
        ...
        ...     def __repr__(self):
        ...         return f"Obj({self.x})"
        >>> PObj = parametric(Obj)

        >>> PObj.mro()
        [<class 'plum.parametric.Obj'>, <class 'plum.parametric.Obj'>,
         <class 'object'>]

        Note that the class `Obj` appears twice in the MRO. The first one is the
        parametric class, and the second one is the non-parametric class. The
        non-parametric class is the original class that was passed to the
        ``parametric`` decorator.

        Rather than navigating the MRO, we can get the non-parametric class of
        an object by calling the ``__class_nonparametric__`` method.

        >>> PObj(1).__class_nonparametric__() is Obj
        True
        """
        return original_class

    def __class_unparametrized__(cls):
        """Return the unparametrized type of an object.

        :mod:`plum.parametric` produces parametric subtypes of classes. This
        method can be used to get the un-parametrized type of an object.

        See Also
        --------
        :func:`plum.type_unparametrized`
            The more-user-friendly function equivalent of this method.
        :func:`plum.type_nonparametric`
            A function to get the non-parametric type of an object.

        Examples
        --------
        In this example we will demonstrate how to retrieve the original
        non-parametric class from a :func:`plum.parametric` decorated class.

        :func:`plum.parametric` defines a parametric class of the same name as
        the original class, and then creates a subclass of the original class
        with the type parameter inferred from the arguments of the constructor.

        >>> from plum import parametric
        >>> class Obj:
        ...     @classmethod
        ...     def __infer_type_parameter__(cls, *arg):
        ...         return type(arg[0])
        ...
        ...     def __init__(self, x):
        ...         self.x = x
        ...
        ...     def __repr__(self):
        ...         return f"Obj({self.x})"
        >>> PObj = parametric(Obj)

        >>> PObj.mro()
        [<class 'plum.parametric.Obj'>, <class 'plum.parametric.Obj'>,
         <class 'object'>]

        Note that the class `Obj` appears twice in the MRO. The first one is the
        non-concrete parametric class, and the second one is the non-parametric
        class. Rather than navigating the MRO, we can get the non-concrete
        parametric class of an object by calling the
        ``__class_unparametrized__`` method.

        >>> PObj(1).__class_unparametrized__() is PObj
        True

        Note that this is still NOT the 'original'
        non-:func:`plum.parametric`-wrapped type.  This is the type that is
        wrapped by :mod:`plum.parametric`, but without the inferred type
        parameter(s).
        """
        return parametric_class

    # Create parametric class.
    parametric_class = meta(
        original_class.__name__,
        (original_class,),
        {
            "__new__": __new__,
            "__init_subclass__": __init_subclass__,
            "__class_nonparametric__": __class_nonparametric__,
            "__class_unparametrized__": __class_unparametrized__,
        },
    )
    parametric_class._parametric = True
    parametric_class._concrete = False
    parametric_class.__module__ = original_class.__module__

    # When dispatch is used in methods of `original_class`, because we return
    # `parametric_class`, `parametric_class` will be inferred as the owner of those
    # functions. This is erroneous, because the owner should be `original_class`. What
    # will happen is that `original_class` will be the next in the MRO, which means
    # that, whenever a `NotFoundLookupError` happens, the method will try itself again,
    # resulting in an infinite loop. To prevent this from happening, we must adjust the
    # owner.
    _owner_transfer[parametric_class] = original_class

    # Attempt to correct docstring.
    with contextlib.suppress(AttributeError):
        parametric_class.__doc__ = original_class.__doc__

    return parametric_class


def is_concrete(t):
    """Check if a type `t` is a concrete instance of a parametric type.

    Args:
        t (type): Type to check.

    Returns:
        bool: `True` if `t` is a concrete instance of a parametric type and `False`
            otherwise.
    """
    return getattr(t, "parametric", False) and t.concrete


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
        beartype.door.TypeHint(x)
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
    t = x if is_type(x) else type(x)
    if hasattr(t, "parametric"):
        return t.type_parameter
    raise ValueError(
        f"`{x}` is not a concrete parametric type or an instance of a"
        f" concrete parametric type."
    )


def type_nonparametric(q: T) -> Type[T]:
    """Return the non-parametric type of an object.

    :mod:`plum.parametric` produces parametric subtypes of classes. This method
    can be used to get the original non-parametric type of an object.

    See Also
    --------
    :func:`plum.type_unparametrized`
        A function that returns the non-concrete, but still parametric, type of
        an object.

    Examples
    --------
    In this example we will demonstrate how to retrieve the original
    non-parametric class from a :func:`plum.parametric` decorated class.

    :func:`plum.parametric` defines a parametric class of the same name as the
    original class, and then creates a subclass of the original class with the
    type parameter inferred from the arguments of the constructor.

    >>> from plum import parametric
    >>> class Obj:
    ...     @classmethod
    ...     def __infer_type_parameter__(cls, *arg):
    ...         return type(arg[0])
    ...
    ...     def __init__(self, x):
    ...         self.x = x
    ...
    ...     def __repr__(self):
    ...         return f"Obj({self.x})"
    >>> PObj = parametric(Obj)
    >>> pobj = PObj(1)

    >>> type(pobj).mro()
    [<class 'plum.parametric.Obj[int]'>, <class 'plum.parametric.Obj'>,
     <class 'plum.parametric.Obj'>, <class 'object'>]

    Note that the class `Obj` appears twice in the MRO. The first one is the
    parametric class, and the second one is the non-parametric class. The
    non-parametric class is the original class that was passed to the
    ``parametric`` decorator.

    Rather than navigating the MRO, we can get the non-parametric class of an
    object by calling ``type_nonparametric`` function.

    >>> type(pobj) is PObj[int]
    True
    >>> type(pobj) is PObj
    False
    >>> type(pobj) is Obj
    False

    >>> type_nonparametric(pobj) is PObj[int]
    False
    >>> type_nonparametric(pobj) is PObj
    False
    >>> type_nonparametric(pobj) is Obj
    True
    """
    return (
        q.__class_nonparametric__()
        if isinstance(type(q), ParametricTypeMeta)
        else type(q)
    )


def type_unparametrized(q: T) -> Type[T]:
    """Return the unparametrized type of an object.

    :mod:`plum.parametric` produces parametric subtypes of classes.  This
    function can be used to get the un-parametrized type of an object.
    This function also works for normal, :mod:`plum.parametric`-wrapped classes.

    See Also
    --------
    :func:`plum.type_nonparametric`
        A function to get the non-parametric type of an object.

    Examples
    --------
    In this example we will demonstrate how to retrieve the original
    non-parametric class from a :func:`plum.parametric` decorated class.

    :func:`plum.parametric` defines a parametric class of the same name as
    the original class, and then creates a subclass of the original class
    with the type parameter inferred from the arguments of the constructor.

    >>> from plum import parametric
    >>> class Obj:
    ...     @classmethod
    ...     def __infer_type_parameter__(cls, *arg):
    ...         return type(arg[0])
    ...
    ...     def __init__(self, x):
    ...         self.x = x
    ...
    ...     def __repr__(self):
    ...         return f"Obj({self.x})"
    >>> PObj = parametric(Obj)
    >>> pobj = PObj(1)

    >>> type(pobj).mro()
    [<class 'plum.parametric.Obj[int]'>, <class 'plum.parametric.Obj'>,
     <class 'plum.parametric.Obj'>, <class 'object'>]

    Note that the class `Obj` appears twice in the MRO. The first one is the
    non-concrete parametric class, and the second one is the non-parametric
    class. Rather than navigating the MRO, we can get the non-concrete
    parametric class of an object by calling the
    ``type_unparametrized`` function.

    >>> type(pobj) is PObj[int]
    True
    >>> type(pobj) is PObj
    False
    >>> type(pobj) is Obj
    False

    >>> type_unparametrized(pobj) is PObj[int]
    False
    >>> type_unparametrized(pobj) is PObj
    True
    >>> type_unparametrized(pobj) is Obj
    False

    Note that this is still NOT the 'original'
    non-:func:`plum.parametric`-wrapped type.  This is the type that is
    wrapped by :mod:`plum.parametric`, but without the inferred type
    parameter(s).
    """
    typ = type(q)
    return q.__class_unparametrized__() if isinstance(typ, ParametricTypeMeta) else typ


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
        # Do not deprecate until beartype#276 is solved
        # warnings.warn(
        #     "`plum.Val` is deprecated and will be removed in a future version. "
        #     "Please use `typing.Literal` instead.",
        #     stacklevel=2,
        # )
        if type(self).concrete:
            if val is not None and type_parameter(self) != val:
                raise ValueError("The value must be equal to the type parameter.")
        else:
            raise ValueError("The value must be specified.")

    def __repr__(self) -> str:
        return repr_short(type(self)) + "()"

    def __eq__(self, other):
        return type(self) == type(other)
