import abc
import inspect
import logging

from .resolvable import Resolvable, Promise
from .util import multihash, Comparable

__all__ = [
    "TypeMeta",
    "VarArgs",
    "promised_type_of",
    "subclasscheck_cache",
    "ComparableType",
    "Union",
    "Type",
    "ResolvableType",
    "PromisedType",
    "deliver_forward_reference",
    "PromisedList",
    "PromisedTuple",
    "ptype",
    "TypeType",
    "is_object",
    "is_type",
]
log = logging.getLogger(__name__)


class TypeMeta(abc.ABCMeta):
    """Types can also be instantiated with indexing."""

    def __getitem__(self, p):
        if isinstance(p, tuple):
            return self(*p)
        else:
            return self(p)


class AbstractType(metaclass=TypeMeta):
    """An abstract class defining the top of the Plum type hierarchy.

    Any instance of a subclass of :class:`.type.AbstractType` will be henceforth
    referred to be of type Plum type or `ptype`.
    """

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
        self.type = ptype(type)

    def __hash__(self):
        return multihash(VarArgs, self.type)

    def __repr__(self):
        return "VarArgs({})".format(repr(self.type))

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


promised_type_of = Promise()  # Resolves to `.parametric.type_of`.
subclasscheck_cache = {}  # Cache results of `__subclasscheck__`.


class ComparableType(AbstractType, Comparable):
    """A Plum type that can be compared to other Plum types."""

    def __le__(self, other):
        return issubclass(self, other)

    def __subclasscheck__(self, subclass):
        # Cache results for performance.
        key = hash(self), hash(subclass)
        try:
            return subclasscheck_cache[key]
        except KeyError:
            check = all([issubclass(t, self.get_types()) for t in subclass.get_types()])
            subclasscheck_cache[key] = check  # Cache result of check.
            return check

    def __instancecheck__(self, instance):
        return issubclass(promised_type_of.resolve()(instance), self)

    @abc.abstractmethod
    def get_types(self):
        """Get the types encapsulated by this Plum type.

        Returns:
            tuple[type]: Types encapsulated.
        """

    def mro(self):
        """Get the MRO.

        Returns:
            tuple[type]: MRO.
        """
        types = self.get_types()
        if len(types) != 1:
            raise RuntimeError("Exactly one type must be encapsulated to get the MRO.")
        return types[0].mro()


class Union(ComparableType):
    """A union of Plum types.

    IMPORTANT:
        `Union` should not be used to generically refer to anything! Use
            `Union[object]` instead.

    Args:
        *types (type or ptype): Types or Plum types to encapsulate.
        alias (str, optional): Give the union a name.
    """

    def __init__(self, *types, alias=None):
        # Lazily convert to a set to avoid resolution errors.
        self._types = tuple(ptype(t) for t in types)

        # Constuct alias if one is given.
        if alias:
            frame = inspect.stack()[1]
            module = inspect.getmodule(frame[0])
            if module:
                self.alias = f"{module.__name__}.{alias}"
            else:  # pragma: no cover
                self.alias = alias
        else:
            self.alias = None

    def _to_set(self):
        if not isinstance(self._types, set):
            self._types = set(self._types)

    def __hash__(self):
        self._to_set()
        if len(self._types) == 1:
            return hash(list(self._types)[0])
        else:
            return multihash(Union, frozenset(self._types))

    def __repr__(self):
        self._to_set()

        # Show the alias if one is given.
        if self.alias is not None:
            return self.alias

        # Otherwise, show all the types it contains.
        if len(self._types) == 1:
            return repr(list(self._types)[0])
        else:
            return "Union[" + ", ".join(repr(t) for t in self._types) + "]"

    def get_types(self):
        self._to_set()
        return sum([t.get_types() for t in self._types], ())

    @property
    def parametric(self):
        self._to_set()
        return any(t.parametric for t in self._types)


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
        return f"{self._type.__module__}.{self._type.__name__}"

    def get_types(self):
        return (self._type,)


class ResolvableType(ComparableType, Resolvable):
    """A resolvable Plum type."""

    def __hash__(self):
        return hash(ptype(self.resolve()))

    def __repr__(self):
        return repr(ptype(self.resolve()))

    def get_types(self):
        return ptype(self.resolve()).get_types()

    @property
    def parametric(self):
        return ptype(self.resolve()).parametric


class PromisedType(ResolvableType, Promise):
    """A promised Plum type."""


_unresolved_forward_references = []


def get_forward_reference(name):
    """Get a type referring to a forward referenced type.

    Args:
        name (str): Name of type.

    Returns:
        ptype: Type referring to `name`.
    """
    reference = ForwardReferencedType(name)
    _unresolved_forward_references.append(reference)
    return reference


def deliver_forward_reference(type):
    """Deliver a forward reference.

    Args:
        type (type): Type to deliver.
    """
    currently_unresolved_forward_references = _unresolved_forward_references.copy()
    _unresolved_forward_references.clear()
    for reference in currently_unresolved_forward_references:
        if reference.name == type.__name__:
            reference.deliver(Type(type))
        else:
            _unresolved_forward_references.append(reference)


class ForwardReferencedType(PromisedType):
    """A Plum type referring to forward-references type.

    Args:
        name (str): Name of the type.

    Attributes:
        name (str): Name of the type.
    """

    def __init__(self, name):
        self.name = name
        PromisedType.__init__(self)


PromisedList = Promise()  # This will resolve to `.parametric.List`.
PromisedTuple = Promise()  # This will resolve to `.parametric.Tuple`.


def ptype(obj):
    """Convert object to a type.

    Args:
        obj (object): Object to convert to type.

    Returns:
        :class:`.type.AbstractType`: Plum type corresponding to `obj`.
    """
    # If `obj` is already a Plum type, we're done.
    if isinstance(obj, AbstractType):
        return obj

    # Handle mapping from `typing` module.
    if hasattr(obj, "__module__") and obj.__module__ == "typing":
        # Print type as string and remove the module prefix.
        obj_str = str(obj)
        if obj_str.startswith("typing."):
            obj_str = str(obj)[len("typing.") :]

        # Dissect the type.
        parts = obj_str.split("[")
        obj_str = parts[0]
        obj_is_parametrised = len(parts) > 1

        # Remove a potential argument.
        obj_str = obj_str.split("(")[0]

        if obj_str[0] == "<":  # pragma: no cover
            # The type is private. This is a type of a `typing` type. This case is
            # necessary for Python 3.7+.
            pass
        elif obj_str in ("Union", "Optional"):
            if obj_is_parametrised:
                return Union(*(ptype(t) for t in obj.__args__))
            else:
                return Union(object)
        elif obj_str == "List":
            if obj_is_parametrised:
                return PromisedList.resolve()(*(ptype(t) for t in obj.__args__))
            else:
                return Type(list)
        elif obj_str == "Tuple":
            if obj_is_parametrised:
                return PromisedTuple.resolve()(*(ptype(t) for t in obj.__args__))
            else:
                return Type(tuple)
        elif obj_str == "ForwardRef" or obj_str == "_ForwardRef":
            # This depends on the implementation below!
            obj = obj.__forward_arg__
        elif obj_str == "Any":
            return Type(object)
        elif obj_str == "Callable":
            return Type(obj)
        else:
            raise NotImplementedError(
                f'There is currently no support for "typing.{obj.__name__}". '
                f"Please open an issue at https://github.com/wesselb/plum/issues"
            )  # pragma: no cover

    # Strings are forward references.
    if isinstance(obj, str):
        return get_forward_reference(obj)

    # If `obj` is a `type`, wrap it in a `Type`.
    if isinstance(obj, type):
        return Type(obj)

    raise RuntimeError(f'Could not convert "{obj}" to a type.')


TypeType = Union[type, AbstractType]
"""ptype: The type of a Plum type, including shorthands."""


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
