import pydoc
import sys
import textwrap
from functools import wraps
from types import MethodType
from typing import Any, Callable, Iterator, List, Optional, Tuple, TypeVar, Union

from .resolver import AmbiguousLookupError, NotFoundLookupError, Resolver
from .signature import Signature, append_default_args, extract_signature
from .type import resolve_type_hint
from .util import TypeHint, repr_short

__all__ = ["Function"]


_promised_convert = None
"""function or None: This will be set to :func:`.parametric.convert`."""

# `typing.Self` is available for Python 3.11 and higher.
try:  # pragma: specific no cover 3.11
    from typing import Self
except ImportError:  # pragma: specific no cover 3.8 3.9 3.10
    Self = TypeVar("Self", bound="Function")

SomeExceptionType = TypeVar("SomeExceptionType", bound=Exception)


def _document(f: Callable) -> str:
    """Generate documentation for a function `f`.

    The generated documentation contains both the function definition and the
    docstring. The docstring is on the same level of indentation of the function
    definition. There will be no trailing newlines.

    If the package :mod:`sphinx` is not imported, then the function definition will
    be preceded by the string `<separator>`.

    If the package :mod:`sphinx` is imported, then the function definition will include
    a Sphinx directive to displays the function definition in a nice way.

    Args:
        f (function): Function.

    Returns:
        str: Documentation for `f`.
    """
    # :class:`pydoc._PlainTextDoc` removes styling. This styling will display
    # erroneously in Sphinx.
    parts = pydoc._PlainTextDoc().document(f).rstrip().split("\n")

    # Separate out the function definition and the lines corresponding to the body.
    title = parts[0]
    body = parts[1:]

    # Remove indentation from every line of the body. This indentation defaults to
    # four spaces.
    body = [line[4:] for line in body]

    # If `sphinx` is imported, assume that we're building the documentation. In that
    # case, display the function definition in a nice way.
    if "sphinx" in sys.modules:
        title = ".. py:function:: " + title + "\n   :noindex:"
    else:
        title = "<separator>\n\n" + title
    title += "\n"  # Add a newline to separate the title from the body.

    # Ensure that there are no trailing newlines. This can happen if the body is empty.
    return "\n".join([title] + body).rstrip()


def _convert(obj: Any, target_type: TypeHint) -> Any:
    """Convert an object to a particular type. Only converts if `target_type` is set.

    Args:
        obj (object): Object to convert.
        target_type (type): Type to convert to.

    Returns:
        object: `object_to_covert` converted to type of `obj_from_target`.
    """
    if target_type is Any:
        return obj
    else:
        return _promised_convert(obj, target_type)


def _change_function_name(f: Callable, name: str) -> Callable:
    """It is not always the case that `f.__name__` is writable. To solve this, first
    create a temporary function that wraps `f` and then change the name.

    Args:
        f (function): Function to change the name of.
        name (str): New name.

    Returns:
        function: Function that wraps `f` and has name `name`.
    """

    @wraps(f)
    def f_renamed(*args, **kw_args):
        return f(*args, **kw_args)

    f_renamed.__name__ = name
    return f_renamed


_owner_transfer = {}
"""dict[type, type]: When the keys of this dictionary are detected as the owner of
a function (see :meth:`Function.owner`), make the corresponding value the owner."""


class MethodsRegistry:
    def __init__(self, function_name: str):
        self._all_methods: List[Tuple[Callable, Optional[Signature], int]] = []
        self._resolver = None
        self._cache = None
        self._function_name = function_name

    def add_method(
        self, method: Callable, signature: Optional[Signature], precedence: int
    ):
        self._all_methods.append((method, signature, precedence))
        # since the list of methods has changed, the resolver and cache are invalidated
        self.invalidate_resolver_and_cache()

    @property
    def methods(self) -> List[Tuple[Callable, Optional[Signature], int]]:
        return self._all_methods

    def invalidate_resolver_and_cache(self):
        self._resolver = None
        self._cache = None

    @property
    def resolver(self) -> Resolver:
        if self._resolver is None:
            self._resolver = Resolver(self.get_all_subsignatures())
        return self._resolver

    @property
    def cache(self) -> dict:
        if self._cache is None:
            self._cache = {}
        return self._cache

    def get_all_subsignatures(self, strict: bool = True) -> Iterator[Signature]:
        # Perform any pending registrations.
        for f, signature, precedence in self._all_methods:

            # Obtain the signature if it is not available.
            if signature is None:
                try:
                    signature = extract_signature(f, precedence=precedence)
                except NameError:
                    if strict:
                        raise
                    else:  # pragma: specific no cover 3.8 3.9
                        # in case we are using from __future__ import annotations
                        continue
            else:
                # Ensure that the implementation is `f`, but make a copy before
                # mutating.
                signature = signature.__copy__()
                signature.implementation = f

            # Ensure that the implementation has the right name, because this name
            # will show up in the docstring.
            if (
                getattr(signature.implementation, "__name__", None)
                != self._function_name
            ):
                signature.implementation = _change_function_name(
                    signature.implementation,
                    self._function_name,
                )

            # Process default values.
            yield from append_default_args(signature, f)

    def doc(self, exclude: Union[Callable, None] = None) -> str:
        """Concatenate the docstrings of all methods of this function. Remove duplicate
        docstrings before concatenating.

        Args:
            exclude (function, optional): Exclude this implementation from the
                concatenation.

        Returns:
            str: Concatenation of all docstrings.
        """
        # Generate all docstrings, possibly excluding `exclude`.
        if sys.version_info < (3, 10):
            strict = True
        else:
            strict = False
        docs = [
            _document(sig.implementation)
            for sig in self.get_all_subsignatures(strict=strict)
            if not (exclude and sig.implementation == exclude)
        ]
        # This can yield duplicates, because of extra methods automatically generated by
        # :func:`.signature.append_default_args`. We remove these by simply only
        # keeping unique docstrings.
        unique_docs = []
        for d in docs:
            if d not in unique_docs:
                unique_docs.append(d)
        # The unique documentations have no trailing newlines, so separate them with
        # a newline.
        return "\n\n".join(unique_docs)


class _FunctionMeta(type):
    """:class:`Function` implements `__doc__`, which overrides the docstring of the
    class. This simple metaclass ensures that `Function.__doc__` still prints as the
    docstring of the class."""

    @property
    def __doc__(self):
        return self._class_doc


class Function(metaclass=_FunctionMeta):
    """A function.

    Args:
        f (function): Function that is wrapped.
        owner (str, optional): Name of the class that owns the function.
    """

    # When we set `__doc__`, we will lose the docstring of the class, so we save it now.
    # Correctly printing the docstring is handled by :class:`_FunctionMeta`.
    _class_doc = __doc__

    _instances = []

    def __init__(self, f: Callable, owner: Optional[str] = None) -> None:
        Function._instances.append(self)

        self._f: Callable = f
        wraps(f)(self)  # Sets `self._doc`.

        # `owner` is the name of the owner. We will later attempt to resolve to
        # which class it actually points.
        self._owner_name: Optional[str] = owner
        self._owner: Optional[type] = None

        # Initialise pending and resolved methods.
        self._methods_registry: MethodsRegistry = MethodsRegistry(self.__name__)

    @property
    def owner(self):
        """object or None: Owner of the function. If `None`, then there is no owner."""
        if self._owner is None and self._owner_name is not None:
            name = self._owner_name.split(".")[-1]
            self._owner = self._f.__globals__[name]
            # Check if the ownership needs to be transferred to another class. This
            # can be very important for preventing infinite loops.
            while self._owner in _owner_transfer:
                self._owner = _owner_transfer[self._owner]
        return self._owner

    @property
    def __doc__(self) -> Optional[str]:
        """str or None: Documentation of the function. This consists of the
        documentation of the function given at initialisation with the documentation
        of all other registered methods appended.

        Upon instantiation, this property is available through `obj.__doc__`.
        """

        # Derive the basis of the docstring from `self._f`, removing any indentation.
        doc = self._doc.strip()
        if doc:
            # Do not include the first line when removing the indentation.
            lines = doc.splitlines()
            doc = lines[0]
            # There might not be more than one line.
            if len(lines) > 1:
                doc += "\n" + textwrap.dedent("\n".join(lines[1:]))

        # Append the docstrings of all other implementations to it. Exclude the
        # docstring from `self._f`, because that one forms the basis (see boave).
        resolver_doc = self._methods_registry.doc(exclude=self._f)
        if resolver_doc:
            # Add a newline if the documentation is non-empty.
            if doc:
                doc = doc + "\n\n"
            doc += resolver_doc
            # Replace separators with horizontal lines of the right length.
            separator_length = max(map(len, doc.splitlines()))
            doc = doc.replace("<separator>", "-" * separator_length)

        # If the docstring is empty, return `None`, which is consistent with omitting
        # the docstring.
        return doc if doc else None

    @__doc__.setter
    def __doc__(self, value: str) -> None:
        # Ensure that `self._doc` remains a string.
        self._doc = value if value else ""

    @property
    def methods(self) -> List[Signature]:
        """list[:class:`.signature.Signature`]: All available methods."""
        return self._methods_registry.resolver.signatures

    @property
    def _resolver(self) -> Resolver:
        return self._methods_registry.resolver

    @property
    def _cache(self) -> dict:
        return self._methods_registry.cache

    def _clear_cache_dict(self):
        self._methods_registry.invalidate_resolver_and_cache()

    def dispatch(
        self: Self, method: Optional[Callable] = None, precedence=0
    ) -> Union[Self, Callable[[Callable], Self]]:
        """Decorator to extend the function with another signature.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to `0`.

        Returns:
            function: Decorator.
        """
        if method is None:
            return lambda m: self.dispatch(m, precedence=precedence)

        self.register(method, precedence=precedence)
        return self

    def dispatch_multi(
        self: Self, *signatures: Union[Signature, Tuple[TypeHint, ...]]
    ) -> Callable[[Callable], Self]:
        """Decorator to extend the function with multiple signatures at once.

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

        def decorator(method):
            # The precedence will not be used, so we can safely set it to `None`.
            for signature in resolved_signatures:
                self.register(method, signature=signature, precedence=None)
            return self

        return decorator

    def clear_cache(self) -> None:
        """Clear cache."""
        self._methods_registry.invalidate_resolver_and_cache()

    def register(
        self, f: Callable, signature: Optional[Signature] = None, precedence=0
    ) -> None:
        """Register a method.

        Either `signature` or `precedence` must be given.

        Args:
            f (function): Function that implements the method.
            signature (:class:`.signature.Signature`, optional): Signature. If it is
                not given, it will be derived from `f`.
            precedence (int, optional): Precedence of the function. If `signature` is
                given, then this argument will not be used. Defaults to `0`.
        """
        self._methods_registry.add_method(f, signature, precedence)

    def _enhance_exception(self, e: SomeExceptionType) -> SomeExceptionType:
        """Enchance an exception by prepending a prefix to the message of the exception
        which specifies that the message is for this function.

        Args:
            e (:class:`Exception`): Exception.

        Returns:
            :class:`Exception`: `e`, but with a prefix appended to the message.
        """
        # Specify to which function the message pertains.
        prefix = f"For function `{self.__name__}`"
        if self.owner:
            prefix += f" of `{repr_short(self.owner)}`"
        prefix = prefix + ", "
        # Return a new exception of the same type which incorporates the prefix.
        message = str(e)
        return type(e)(prefix + message[0].lower() + message[1:])

    def resolve_method(
        self, target: Union[Tuple[object, ...], Signature]
    ) -> Tuple[Callable, TypeHint]:
        """Find the method and return type for arguments.

        Args:
            target (object): Target.

        Returns:
            function: Method.
            type: Return type.
        """
        try:
            # Attempt to find the method using the resolver.
            signature = self._methods_registry.resolver.resolve(target)
            method = signature.implementation
            return_type = signature.return_type

        except AmbiguousLookupError as e:
            raise self._enhance_exception(e)  # Specify this function.

        except NotFoundLookupError as e:
            e = self._enhance_exception(e)  # Specify this function.
            method, return_type = self._handle_not_found_lookup_error(e)

        return method, return_type

    def _handle_not_found_lookup_error(
        self, ex: NotFoundLookupError
    ) -> Tuple[Callable, TypeHint]:
        if not self.owner:
            # Not in a class. Nothing we can do.
            raise ex

        # In a class. Walk through the classes in the class's MRO, except for this
        # class, and try to get the method.
        method = None
        return_type = object

        for c in self.owner.__mro__[1:]:
            # Skip the top of the type hierarchy given by `object` and `type`. We do
            # not suddenly want to fall back to any unexpected default behaviour.
            if c in {object, type}:
                continue

            # We need to check `c.__dict__` here instead of using `hasattr` since e.g.
            # `c.__le__` will return  even if `c` does not implement `__le__`!
            if self._f.__name__ in c.__dict__:
                method = getattr(c, self._f.__name__)
            else:
                # For some reason, coverage fails to catch the `continue` below. Add
                # the do-nothing `_ = None` fixes this.
                # TODO: Remove this once coverage properly catches this.
                _ = None
                continue

            # Ignore abstract methods.
            if getattr(method, "__isabstractmethod__", False):
                method = None
                continue

            # We found a good candidate. Break.
            break

        if not method:
            # If no method has been found after walking through the MRO, raise the
            # original exception.
            raise ex
        return method, return_type

    def __call__(self, *args: object, **kw_args: object) -> object:
        method, return_type = self._resolve_method_with_cache(args=args)
        return _convert(method(*args, **kw_args), return_type)

    def _resolve_method_with_cache(
        self,
        args: Union[Tuple[object, ...], Signature, None] = None,
        types: Optional[Tuple[TypeHint, ...]] = None,
    ) -> Tuple[Callable, TypeHint]:
        if args is None and types is None:
            raise ValueError(
                "Arguments `args` and `types` cannot both be `None`. "
                "This should never happen!"
            )

        if types is None:
            # Attempt to use the cache based on the types of the arguments.
            types = tuple(map(type, args))
        try:
            return self._cache[types]
        except KeyError:
            if args is None:
                args = Signature(*(resolve_type_hint(t) for t in types))

            # Cache miss. Run the resolver based on the arguments.
            method, return_type = self.resolve_method(args)
            # If the resolver is faithful, then we can perform caching using the types
            # of the arguments. If the resolver is not faithful, then we cannot.
            if self._resolver.is_faithful:
                self._cache[types] = method, return_type
            return method, return_type

    def invoke(self, *types: TypeHint) -> Callable:
        """Invoke a particular method.

        Args:
            *types: Types to resolve.

        Returns:
            function: Method.
        """
        method, return_type = self._resolve_method_with_cache(types=types)

        @wraps(self._f)
        def wrapped_method(*args, **kw_args):
            return _convert(method(*args, **kw_args), return_type)

        return wrapped_method

    def __get__(self, instance, owner):
        if instance is not None:
            return MethodType(_BoundFunction(self, instance), instance)
        else:
            return self

    def __repr__(self) -> str:
        return (
            f"<function {self._f} with {len(self._methods_registry.methods)} method(s)>"
        )


class _BoundFunction:
    """A bound instance of `.function.Function`.

    Args:
        f (:class:`.function.Function`): Bound function.
        instance (object): Instance to which the function is bound.
    """

    def __init__(self, f, instance):
        self._f = f
        wraps(f._f)(self)  # This will call the setter for `__doc__`.
        self._instance = instance

    @property
    def __doc__(self):
        return self._f.__doc__

    @__doc__.setter
    def __doc__(self, value):
        # Don't need to do anything here. The docstring will be derived from `self._f`.
        # We, however, do need to implement this method, because :func:`wraps` calls
        # it.
        pass

    def __call__(self, _, *args, **kw_args):
        return self._f(self._instance, *args, **kw_args)

    def invoke(self, *types):
        """See :meth:`.Function.invoke`."""

        @wraps(self._f._f)
        def wrapped_method(*args, **kw_args):
            # TODO: Can we do this without `type` here?
            method = self._f.invoke(type(self._instance), *types)
            return method(self._instance, *args, **kw_args)

        return wrapped_method
