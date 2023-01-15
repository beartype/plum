import sys
import typing
import warnings

try:  # pragma: no cover
    from collections.abc import Callable
except ImportError:  # pragma: no cover
    from typing import Callable  # Python 3.8 and earlier


__all__ = [
    "PromisedType",
    "ModuleType",
    "type_mapping",
    "resolve_type_hint",
    "is_faithful",
]


class ResolvableType(type):
    """A resolvable type that will resolve to `type` after `type` has been delivered via
    :meth:`.ResolvableType.deliver`. Before then, it will resolve to itself.

    Args:
        name (str): Name of the type to be delivered.
    """

    def __init__(self, name):
        type.__init__(self, name, (), {})
        self._type = None

    def __new__(self, name):
        return type.__new__(self, name, (), {})

    def deliver(self, type):
        """Deliver the type.

        Args:
            type (type): Type to deliver.

        Returns:
            :class:`ResolvableType`: `self`.
        """
        self._type = type
        return self

    def resolve(self):
        """Resolve the type.

        Returns:
            type: If no type has been delivered, this will return itself. If a type
                `type` has been delivered via :meth:`.ResolvableType.deliver`, this will
                return that type.
        """
        if self._type is None:
            return self
        else:
            return self._type


class PromisedType(ResolvableType):
    """A type that is promised to be available when you will you need it.

    Args:
        name (str): Name of the type that is promised.
    """

    def __init__(self, name):
        ResolvableType.__init__(self, f"PromisedType[{name}]")
        self._name = name

    def __new__(cls, name):
        return ResolvableType.__new__(cls, f"PromisedType[{name}]")


class ModuleType(ResolvableType):
    """A type from another module.

    Args:
        module (str): Module that the type lives in.
        name (str): Name of the type that is promised.
    """

    def __init__(self, module, name):
        if module in {"__builtin__", "__builtins__"}:
            module = "builtins"
        ResolvableType.__init__(self, f"ModuleType[{module}.{name}]")
        self._name = name
        self._module = module

    def __new__(cls, module, name):
        return ResolvableType.__new__(cls, f"ModuleType[{module}.{name}]")

    def retrieve(self):
        """Attempt to retrieve the type from the reference module.

        Returns:
            :class:`ModuleType`: `self`.
        """
        if self._type is None:
            if self._module in sys.modules:
                type = sys.modules[self._module]
                for name in self._name.split("."):
                    type = getattr(type, name)
                self.deliver(type)
        return self


def _is_hint(x):
    """Check if an object is a type hint.

    Args:
        x (object): Object.

    Returns:
        bool: `True` if `x` is a type hint and `False` otherwise.
    """
    return hasattr(x, "__module__") and x.__module__ in {"typing", "collections.abc"}


def _hashable(x):
    """Check if an object is hashable.

    Args:
        x (object): Object to check.

    Returns:
        bool: `True` if `x` is hashable and `False` otherwise.
    """
    try:
        hash(x)
        return True
    except TypeError:
        return False


type_mapping = {}
"""dict[type, type]: When running :func:`resolve_type_hint`, map keys in this dictionary
to the values."""


def resolve_type_hint(x):
    """Resolve all :class:`ResolvableType` in a type hint.

    If a type hint is not supported by this function, then the resolution process will
    end early to not break your code. In that case, a warning will be thrown saying
    that there may still be some remaining :class:`ResolvableType`s.

    Args:
        x (object): Type hint.

    Returns:
        object: `x`, but with all :class:`ResolvableType` resolved.
    """
    if _hashable(x) and x in type_mapping:
        return resolve_type_hint(type_mapping[x])
    elif _is_hint(x):
        origin = typing.get_origin(x)
        args = typing.get_args(x)
        if args == ():
            # `origin` might not make sense here. For example, `get_origin(Any)` is
            # `None`. Since the hint wasn't subscripted, the right thing is to right the
            # hint itself.
            return x
        else:
            return origin[resolve_type_hint(args)]

    elif x is None:
        return x
    elif x is Ellipsis:
        return x

    elif isinstance(x, tuple):
        return tuple(resolve_type_hint(arg) for arg in x)
    elif isinstance(x, list):
        return list(resolve_type_hint(arg) for arg in x)
    elif isinstance(x, type):
        if isinstance(x, ResolvableType):
            if isinstance(x, ModuleType):
                x.retrieve()
            return resolve_type_hint(x.resolve())
        else:
            return x

    else:
        warnings.warn(
            f"Could not resolve the type hint of `{x}`. "
            f"I have ended the resolution here to not make your code break, but some "
            f"types might not be working correctly. "
            f"Please open an issue at https://github.com/wesselb/plum."
        )
        return x


def is_faithful(x):
    """Check whether a type hint is faithful.

    If a type hint is not supported by this function, then the function will return
    early to not break your code. In that case, a warning will be thrown saying that the
    dispatch performance may be subpar.

    Args:
        x (object): Type hint.

    Returns:
        bool: Whether `x` is faithful or not.
    """
    return _is_faithful(resolve_type_hint(x))


def _is_faithful(x):
    if _is_hint(x):
        origin = typing.get_origin(x)
        args = typing.get_args(x)
        if args == ():
            # Unsubscripted type hints tend to be faithful. For example, `Any`, `List`,
            # `Tuple`, `Dict`, `Callable`, and `Generator` are. When we come across a
            # counter-example, we will refine this logic.
            return True
        else:
            if origin in {typing.Union, typing.Optional}:
                return all(is_faithful(arg) for arg in args)
            else:
                return False

    elif x is None:
        return True
    elif x == Ellipsis:
        return True

    elif isinstance(x, (tuple, list)):
        return all(is_faithful(arg) for arg in x)
    elif isinstance(x, type):
        return True

    else:
        warnings.warn(
            f"Could not determine whether `{x}` is faithful or not. "
            f"I have concluded that the type is not faithful, so your code might run "
            f"with subpar performance. "
            f"Please open an issue at https://github.com/wesselb/plum."
        )
        return False
