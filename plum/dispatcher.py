import sys
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field, replace
from functools import partial
from itertools import chain
from typing import Any, Dict, Optional, Tuple, TypeVar, Union, final, overload

from .function import Function
from .overload import get_overloads
from .signature import Signature
from .util import Callable, TypeHint, get_class, is_in_class

__all__ = [
    "AbstractDispatcher",
    "Dispatcher",
    "DispatcherBundle",
    "dispatch",
    "clear_all_cache",
]

T = TypeVar("T", bound=Callable[..., Any])


_dataclass_kw_args: Dict[str, Any] = {}
if sys.version_info >= (3, 10):  # pragma: specific no cover 3.8 3.9
    _dataclass_kw_args |= {"slots": True}


@dataclass(frozen=True, **_dataclass_kw_args)
class AbstractDispatcher(metaclass=ABCMeta):
    """An abstract dispatcher."""

    @overload
    def __call__(self, method: T, precedence: int = ...) -> T: ...

    @overload
    def __call__(self, method: None, precedence: int) -> Callable[[T], T]: ...

    @abstractmethod
    def __call__(
        self, method: Optional[T] = None, precedence: int = 0
    ) -> Union[T, Callable[[T], T]]: ...

    @abstractmethod
    def abstract(self, method: Callable) -> Function:
        """Decorator for an abstract function definition. The abstract function
        definition does not implement any methods."""

    @abstractmethod
    def multi(
        self, *signatures: Union[Signature, Tuple[TypeHint, ...]]
    ) -> Callable[[Callable], Function]:
        """Decorator to register multiple signatures at once."""

    @abstractmethod
    def clear_cache(self) -> None:
        """Clear cache."""


@final
@dataclass(frozen=True, **_dataclass_kw_args)
class Dispatcher(AbstractDispatcher):
    """A namespace for functions.

    Args:
        warn_redefinition (bool, optional): Throw a warning whenever a method is
            redefined. Defaults to `False`.

    Attributes:
        functions (dict[str, :class:`.function.Function`]): Functions by name.
        classes (dict[str, dict[str, :class:`.function.Function`]]): Methods of
            all classes by the qualified name of a class.
        warn_redefinition (bool): Throw a warning whenever a method is redefined.
    """

    warn_redefinition: bool = False
    functions: Dict[str, Function] = field(default_factory=dict)
    classes: Dict[str, Dict[str, Function]] = field(default_factory=dict)

    @overload
    def __call__(self, method: T, precedence: int = ...) -> T: ...

    @overload
    def __call__(self, method: None, precedence: int) -> Callable[[T], T]: ...

    def __call__(
        self, method: Optional[T] = None, precedence: int = 0
    ) -> Union[T, Callable[[T], T]]:
        """Decorator to register for a particular signature.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to `0`.

        Returns:
            function: Decorator.
        """
        if method is None:
            return partial(self.__call__, precedence=precedence)

        # If `method` has overloads, assume that those overloads need to be registered
        # and that `method` is not an implementation.
        overloads = get_overloads(method)
        if overloads:
            for overload_method in overloads:
                # All `f` returned by `self._add_method` are the same.
                f = self._add_method(overload_method, None, precedence=precedence)
            # We do not need to register `method`, because it is not an implementation.
            return f

        # The signature will be automatically derived from `method`, so we can safely
        # set the signature argument to `None`.
        return self._add_method(method, None, precedence=precedence)

    def multi(
        self, *signatures: Union[Signature, Tuple[TypeHint, ...]]
    ) -> Callable[[Callable], Function]:
        """Decorator to register multiple signatures at once.

        Args:
            *signatures (tuple or :class:`.signature.Signature`): Signatures to
                register.

        Returns:
            function: Decorator.
        """
        resolved_signatures = []
        for signature in signatures:
            if isinstance(signature, Signature):
                resolved_signatures.append(signature)
            elif isinstance(signature, tuple):
                resolved_signatures.append(Signature(*signature))
            else:
                raise ValueError(
                    f"Signature `{signature}` must be a tuple or of type "
                    f"`plum.signature.Signature`."
                )

        def decorator(method: Callable) -> Function:
            # The precedence will not be used, so we can safely set it to `None`.
            return self._add_method(method, *resolved_signatures, precedence=None)

        return decorator

    def abstract(self, method: Callable) -> Function:
        """Decorator for an abstract function definition. The abstract function
        definition does not implement any methods."""
        return self._get_function(method)

    def _get_function(self, method: Callable) -> Function:
        # If a class is the owner, use a namespace specific for that class. Otherwise,
        # use the global namespace.
        if is_in_class(method):
            owner = get_class(method)
            if owner not in self.classes:
                self.classes[owner] = {}
            namespace = self.classes[owner]
        else:
            owner = None
            namespace = self.functions

        # Create a new function only if the function does not already exist.
        name = method.__name__
        if name not in namespace:
            namespace[name] = Function(
                method,
                owner=owner,
                warn_redefinition=self.warn_redefinition,
            )

        return namespace[name]

    def _add_method(
        self,
        method: Callable,
        *signatures: Optional[Signature],
        precedence: Optional[int],
    ) -> Function:
        f = self._get_function(method)
        for signature in signatures:
            f.register(method, signature, precedence)
        return f

    def clear_cache(self) -> None:
        """Clear cache."""
        for f in self.functions.values():
            f.clear_cache()

    def __or__(self, other: "AbstractDispatcher") -> "DispatcherBundle":
        if not isinstance(other, AbstractDispatcher):
            raise ValueError(f"Cannot combine `Dispatcher` with `{type(other)}`.")
        return DispatcherBundle.from_dispatchers(self, other)


@final
@dataclass(frozen=True, **_dataclass_kw_args)
class DispatcherBundle(AbstractDispatcher):
    """A bundle of dispatchers.

    Examples
    --------
    A DispatcherBundle allows for different dispatchers to share a method, even
    when their other methods are different. In this example `f(int, int)` is
    shared between `dispatch1` and `dispatch2`, while the following methods are
    unique to each dispatcher.

    >>> from plum import Dispatcher
    >>> from types import SimpleNamespace

    In one namespace:

    >>> dispatch1 = Dispatcher()

    >>> @dispatch1
    ... def f(x: int, y: float) -> int:
    ...     return x + int(y)

    >>> ns1 = SimpleNamespace(f=f)

    In another namespace:

    >>> dispatch2 = Dispatcher()

    >>> @dispatch2
    ... def f(x: float, y: int) -> float:
    ...     return x + float(y)

    >>> ns2 = SimpleNamespace(f=f)

    Here we want to share the `f(int, int)` method between `dispatch1` and
    `dispatch2`. This can be done with a `DispatcherBundle`, which combines the
    dispatchers. A `DispatcherBundle` can be created with the `|` operator.

    >>> @(dispatch1 | dispatch2)
    ... def f(x: int, y: int) -> int:
    ...     return x + y

    The function `f` is registered in both dispatchers.

    >>> dispatch1.functions
    {'f': ...}

    >>> dispatch2.functions
    {'f': ...}

    .. note::

        The :class:`plum.Function` object depends on the dispatch order. Here
        `dispatch1` is the first dispatcher and `dispatch2` is the second.
        Therefore, the returned function is the one registered last, which is
        the one in `dispatch2`.


    In application:

    >>> ns1.f(1, 2)  # From dispatch1/2, depending on the namespace.
    3

    >>> ns2.f(1, 2)
    3

    >>> ns1.f(1, 2.0)  # From dispatch1.
    3

    >>> ns2.f(1.0, 2)  # From dispatch2.
    3.0

    At least one dispatcher must be provided to `DispatcherBundle`.

    >>> from plum import DispatcherBundle

    >>> try:
    ...     DispatcherBundle(())
    ... except ValueError as e:
    ...     print(e)
    At least one dispatcher must be provided to DispatcherBundle.


    A `DispatcherBundle` can be created from a sequence of dispatchers.

    >>> dispatchbundle = DispatcherBundle.from_dispatchers(dispatch1, dispatch2)

    A nested `DispatcherBundle` can be flattened.

    >>> dispatch3 = Dispatcher()
    >>> dispatchbundle = DispatcherBundle((dispatchbundle, dispatch3))
    >>> dispatchbundle
    DispatcherBundle(dispatchers=(DispatcherBundle(dispatchers=(Dispatcher(...), Dispatcher(...))), Dispatcher(...)))


    >>> dispatchbundle = dispatchbundle.flatten()
    >>> dispatchbundle
    DispatcherBundle(dispatchers=(Dispatcher(...), Dispatcher(...), Dispatcher(...)))

    :class:`plum.DispatcherBundle`s can be combined with `|`. They are flattened
    automatically.

    >>> dispatch4 = Dispatcher()
    >>> dispatchbundle1 = dispatch1 | dispatch2
    >>> dispatchbundle2 = dispatch3 | dispatch4
    >>> dispatchbundle = dispatchbundle1 | dispatchbundle2
    >>> dispatchbundle
    DispatcherBundle(dispatchers=(Dispatcher(...), Dispatcher(...), Dispatcher(...), Dispatcher(...)))

    """  # noqa: E501

    dispatchers: Tuple[AbstractDispatcher, ...]

    def __post_init__(self) -> None:
        if not self.dispatchers:
            msg = "At least one dispatcher must be provided to DispatcherBundle."
            raise ValueError(msg)

    @classmethod
    def from_dispatchers(cls, *dispatchers: AbstractDispatcher) -> "DispatcherBundle":
        """Create a `DispatcherBundle` from a sequence of dispatchers.

        This also flattens nested `DispatcherBundle`s.
        """

        return cls(dispatchers).flatten()

    def flatten(self) -> "DispatcherBundle":
        """Flatten the bundle."""

        def as_seq(x: AbstractDispatcher) -> Tuple[AbstractDispatcher, ...]:
            return x.dispatchers if isinstance(x, DispatcherBundle) else (x,)

        return replace(
            self, dispatchers=tuple(chain.from_iterable(map(as_seq, self.dispatchers)))
        )

    @overload
    def __call__(self, method: T, precedence: int = ...) -> T: ...

    @overload
    def __call__(self, method: None, precedence: int) -> Callable[[T], T]: ...

    def __call__(
        self, method: Optional[T] = None, precedence: int = 0
    ) -> Union[T, Callable[[T], T]]:
        for dispatcher in self.dispatchers:
            f = dispatcher(method, precedence=precedence)
        return f

    def abstract(self, method: Callable) -> Function:
        """Decorator for an abstract function definition. The abstract function
        definition does not implement any methods."""
        for dispatcher in self.dispatchers:
            f = dispatcher.abstract(method)
        return f

    def multi(
        self, *signatures: Union[Signature, Tuple[TypeHint, ...]]
    ) -> Callable[[Callable], Function]:
        """Decorator to register multiple signatures at once.

        Args:
            *signatures (tuple or :class:`.signature.Signature`): Signatures to
                register.

        Returns:
            function: Decorator.
        """

        def decorator(method: Callable) -> Function:
            for dispatcher in self.dispatchers:
                f = dispatcher.multi(*signatures)(method)
            return f

        return decorator

    def clear_cache(self) -> None:
        """Clear cache."""
        for dispatcher in self.dispatchers:
            dispatcher.clear_cache()

    def __or__(self, other: "AbstractDispatcher") -> "DispatcherBundle":
        if not isinstance(other, AbstractDispatcher):
            return NotImplemented
        return self.from_dispatchers(self, other)


def clear_all_cache():
    """Clear all cache, including the cache of subclass checks. This should be called
    if types are modified."""
    for f in Function._instances:
        f.clear_cache()


dispatch = Dispatcher()  #: A default dispatcher for convenience purposes.
