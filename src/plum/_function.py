__all__ = ("Function",)

import os
import textwrap
import threading
from collections.abc import Callable
from copy import copy
from functools import WRAPPER_ASSIGNMENTS, partial
from types import MethodType
from typing import Any, ClassVar, Protocol, TypeVar, overload
from typing_extensions import Self

from ._method import Method, MethodList
from ._mypyc import mypyc_attr
from ._resolver import AmbiguousLookupError, NotFoundLookupError, Resolver
from ._signature import Signature, append_default_args
from ._type import resolve_type_hint
from ._util import TypeHint

_INVOKE_CACHE_LIMIT = 4096
"""Maximum number of wrappers cached for one function.

Unlike `_cache`, this is not gated on `is_faithful`, so it fills for functions whose
method cache stays empty. The keys are whatever type hints callers pass, and
`_BoundInvokedMethod` adds one per `(type(instance), *types)` combination, so for a
process-global function such as `_promotion._convert` the key space is bounded only by
the caller's data. Past this many, `invoke` simply rebuilds its wrapper each time --
exactly what it did before this cache existed, so no call can get a wrong answer."""


# Annotated (not left to inference as `None`) so a `mypyc`-compiled `_function` accepts
# the external assignment `plum._function._promised_convert = convert` in `_promotion`.
_promised_convert: Callable[..., Any] | None = None
"""function or None: This will be set to :func:`.parametric.convert`."""

SomeExceptionType = TypeVar("SomeExceptionType", bound=Exception)


def _convert(obj: Any, target_type: TypeHint, /) -> Any:
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
        assert _promised_convert is not None
        return _promised_convert(obj, target_type)


_owner_transfer: dict[type, type] = {}
"""dict[type, type]: When the keys of this dictionary are detected as the owner of
a function (see :meth:`Function.owner`), make the corresponding value the owner."""


_HAS_ANNOTATE = "__annotate__" in WRAPPER_ASSIGNMENTS
"""Whether this interpreter carries annotations lazily on `__annotate__`.

Python 3.14 replaced `__annotations__` with `__annotate__` in
`functools.WRAPPER_ASSIGNMENTS`, so this reads the answer off `functools` itself
rather than testing the version. :func:`_wraps` follows whichever this interpreter's
`functools.wraps` uses, so a wrapper is observationally the same on every supported
version -- and so that annotations are never forced to materialise, which on 3.14 can
raise for a forward reference that is not resolvable yet."""


def _wraps(wrapper: Any, wrapped: Callable[..., Any], /) -> None:
    """Copy `wrapped`'s metadata onto `wrapper`, like :func:`functools.wraps`.

    `functools.wraps` costs about 1.1 us, and almost all of it goes on work nothing
    here needs: it walks `WRAPPER_ASSIGNMENTS` with a `try`/`except` per name,
    copies `__annotate__` and `__type_params__`, and merges the wrapped function's
    `__dict__`. What plum and :func:`inspect.signature` actually read is the four
    names below plus `__wrapped__`, which straight-line assignment writes in about
    0.43 us -- 2.5x less. Annotations and the `__dict__` merge are kept, so what a
    caller can observe on the wrapper is unchanged. The one thing not copied is
    `__type_params__`, which nothing here reads and which costs 0.09 us on its own.

    This is the default. :func:`_wraps_native` is the cut-down version for a
    `mypyc` native class, whose instances cannot take all of these.

    Args:
        wrapper (object): Object to copy metadata onto.
        wrapped (Callable): Function to copy metadata from.
    """
    wrapper.__module__ = wrapped.__module__
    wrapper.__name__ = wrapped.__name__
    try:
        # A callable object need not have `__qualname__`; `Function` only requires
        # `__name__`. `try` rather than `getattr(..., default)`, whose default is
        # evaluated on every call and costs more than the attribute it guards.
        wrapper.__qualname__ = wrapped.__qualname__
    except AttributeError:
        wrapper.__qualname__ = wrapped.__name__
    wrapper.__doc__ = wrapped.__doc__
    try:
        if _HAS_ANNOTATE:
            # `unused-ignore` as well: `__annotate__` exists only from Python 3.14,
            # so `mypy` flags the attribute below 3.14 and flags the ignore above it.
            wrapper.__annotate__ = wrapped.__annotate__  # type: ignore[attr-defined, unused-ignore]
        else:
            wrapper.__annotations__ = wrapped.__annotations__
    except AttributeError:
        # A callable object need not carry annotations at all.
        pass
    # Last, and in this order, exactly as `functools.wraps` does it: a `__wrapped__`
    # in `wrapped.__dict__` must not win over the one set here. It is the single most
    # expensive line here -- 0.15 of the 0.43 us -- and the only one kept purely for
    # parity.
    #
    # Only the *read* is guarded. `functools.wraps` tolerates a `wrapped` without a
    # `__dict__`, such as a slotted callable, so this must too; it does not tolerate a
    # `wrapper` without one, and neither should this. That second half is structural
    # rather than observable: `__module__` cannot go in `__slots__`, so a wrapper with
    # no `__dict__` already fails on the first assignment above and never reaches
    # here. Guarding only the read is still the honest shape -- a wrapper-side
    # `AttributeError` is a mistake and must not be swallowed.
    try:
        attrs = wrapped.__dict__
    except AttributeError:
        pass
    else:
        wrapper.__dict__.update(attrs)
    wrapper.__wrapped__ = wrapped


class _NativeWrappable(Protocol):
    __name__: str
    __qualname__: str
    __wrapped__: Callable[..., Any]


def _wraps_native(wrapper: _NativeWrappable, wrapped: Callable[..., Any], /) -> None:
    """:func:`_wraps` for a `mypyc` native class, which can take less.

    A native instance has no `__dict__` and a read-only `__module__`, and serves
    `__doc__` from a descriptor, so the three names below are both all that can be
    written and all that is needed. It also takes the *generated* qualified name
    rather than the wrapped function's own; see :func:`_generate_qualname`.

    Use :func:`_wraps` for anything else.

    Args:
        wrapper (object): Native instance to copy metadata onto.
        wrapped (Callable): Function to copy metadata from.
    """
    wrapper.__name__ = wrapped.__name__
    wrapper.__qualname__ = _generate_qualname(wrapped)
    wrapper.__wrapped__ = wrapped


@mypyc_attr(native_class=False)
class _InvokedMethod:
    """Run the resolved `method` and convert the result.

    Callable returned by :meth:`Function.invoke`. A class rather than a closure,
    which `mypyc` cannot compile (mypyc/mypyc#1205); non-native so :func:`_wraps` can
    copy `__name__`/`__doc__` onto instances.
    """

    def __init__(
        self, f: Callable[..., Any], method: Callable[..., Any], return_type: TypeHint
    ) -> None:
        self._method = method
        self._return_type = return_type
        _wraps(self, f)
        self.__wrapped_by_plum__ = method

    def __call__(self, *args: Any, **kw: Any) -> Any:
        return _convert(self._method(*args, **kw), self._return_type)


class _DocDescriptor:
    """Serve `__doc__`: `_class_doc` on class access, `_compute_doc()` on instances.

    Shared by `Function` and `_BoundFunction`.
    """

    def __get__(self, instance: Any, owner: type) -> str | None:
        if instance is None:
            return getattr(owner, "_class_doc", None)
        doc: str | None = instance._compute_doc()
        return doc


@mypyc_attr(native_class=False)
class _ModuleDescriptor(str):
    """Serve `__module__` as the wrapped function's module on instance access.

    Shared by `Function` and `_BoundFunction`.

    A `str` subclass because CPython returns a class-level `__module__` verbatim
    without calling `__get__`, so the value itself must be a valid module string for
    tools like Sphinx; instance access does call `__get__`. (A `str` subclass is
    non-native, but `__module__` access is not on the hot path.)
    """

    __slots__ = ()

    def __get__(self, instance: Any, owner: type) -> str:
        module: str = instance._f.__module__
        return module


class Function:
    #: The class-level docstring, served as `Function.__doc__` by `_DocDescriptor`.
    _class_doc: ClassVar[str] = """A function.

    Args:
        f (function): Function that is wrapped.
        owner (str, optional): Name of the class that owns the function.
        warn_redefinition (bool, optional): Throw a warning whenever a method is
            redefined. Defaults to `False`.
    """

    _instances: ClassVar[list["Function"]] = []

    # Instance attributes are declared so `Function` can be a `mypyc` native class.
    _f: Callable[..., Any]
    _cache: dict[tuple[TypeHint, ...], tuple[Callable[..., Any], TypeHint]]
    _generation: int
    _invoke_cache: dict[tuple[TypeHint, ...], "_InvokedMethod"]
    _doc: str
    _owner_name: str | None
    _owner: type | None
    _warn_redefinition: bool
    _pending: list[tuple[Callable[..., Any], Signature | None, int | None]]
    _resolved: list[tuple[Callable[..., Any], Signature | None, int | None]]
    _resolver: Resolver
    _lock: threading.RLock
    __name__: str
    __qualname__: str
    __wrapped__: Callable[..., Any]

    def __init__(
        self,
        f: Callable[..., Any],
        /,
        owner: str | None = None,
        warn_redefinition: bool = False,
    ) -> None:
        Function._instances.append(self)

        self._f = f
        # Cache maps type tuples to `(method, return_type)`. Keys can be either
        # actual types (from `__call__`) or `TypeHints` (from `invoke`).
        self._cache = {}
        # Bumped by `clear_cache`, under the lock. A resolution that started before a
        # concurrent clear compares this before storing, so it cannot write an answer
        # the clear was meant to discard. Guards both caches below.
        self._generation = 0
        # `invoke` returns the same wrapper for the same types, so it is built once.
        self._invoke_cache = {}

        # Guards the lazy resolution of pending registrations, which mutates each
        # registered function's `__annotations__` in place (via beartype's
        # `resolve_pep563`) and is otherwise not thread-safe. Reentrant because
        # `_resolve_pending_registrations` calls `clear_cache`, which also acquires this
        # lock. See GitHub issue #274.
        self._lock = threading.RLock()

        # `__doc__` is the `_DocDescriptor`, so store the raw docstring in `self._doc`.
        _wraps_native(self, f)
        self._doc = f.__doc__ if f.__doc__ else ""

        # `owner` is the name of the owner. We will later attempt to resolve to
        # which class it actually points.
        self._owner_name = owner
        self._owner = None

        self._warn_redefinition = warn_redefinition

        # Initialise pending and resolved methods.
        self._pending = []
        self._resolver = Resolver(
            self.__name__,
            warn_redefinition=self._warn_redefinition,
        )
        self._resolved = []

    @property
    def owner(self) -> type | None:
        """object or None: Owner of the function. If `None`, then there is no owner."""
        if self._owner is None and self._owner_name is not None:
            name = self._owner_name.split(".")[-1]
            self._owner = self._f.__globals__[name]
            # Check if the ownership needs to be transferred to another class. This
            # can be very important for preventing infinite loops.
            while self._owner in _owner_transfer:
                self._owner = _owner_transfer[self._owner]
        return self._owner

    def _compute_doc(self) -> str | None:
        """Compute the function's documentation.

        This is the documentation given at initialisation, with the documentation of
        all other registered methods appended.
        """
        try:
            self._resolve_pending_registrations()
        except NameError:
            # When `staticmethod` is combined with `from __future__ import
            # annotations`, in Python 3.10 and higher `staticmethod` will
            # attempt to inherit `__doc__` (see
            # https://docs.python.org/3/library/functions.html#staticmethod).
            # Since we are still in class construction, forward references are
            # not yet defined, so attempting to resolve all pending methods
            # might fail with a `NameError`. This is fine, because later calling
            # `__doc__` on the `staticmethod` will again call this `__doc__`, at
            # which point all methods will resolve properly. For now, we just
            # ignore the error and undo the partially completed
            # :meth:`Function._resolve_pending_registrations` by clearing the
            # cache.
            self.clear_cache(reregister=False)

        # Don't do any fancy appending of docstrings when the environment variable
        # `PLUM_SIMPLE_DOC` is set to `1`.
        if "PLUM_SIMPLE_DOC" in os.environ and os.environ["PLUM_SIMPLE_DOC"] == "1":
            return self._doc

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
        resolver_doc = self._resolver.doc(exclude=self._f)
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

    @property
    def methods(self) -> MethodList:
        """list[:class:`.method.Method`]: All available methods."""
        self._resolve_pending_registrations()
        return self._resolver.methods

    def dispatch(
        self: Self, method: Callable[..., Any] | None = None, precedence: int = 0
    ) -> Self | Callable[[Callable[..., Any]], Self]:
        """Decorator to extend the function with another signature.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to `0`.

        Returns:
            function: Decorator.
        """
        if method is None:
            return partial(self._register_one, precedence=precedence)
        return self._register_one(method, precedence=precedence)

    def dispatch_multi(
        self: Self, *signatures: Signature | tuple[TypeHint, ...]
    ) -> Callable[[Callable[..., Any]], Self]:
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
                # `TypeError` (not `ValueError`) to match the compiled build, where the
                # typed vararg rejects bad input at the C boundary before this runs.
                raise TypeError(
                    f"Signature `{signature}` must be a tuple or of type "
                    f"`plum.signature.Signature`."
                )
        return partial(self._register_multiple, signatures=resolved_signatures)

    def _register_one(
        self: Self, method: Callable[..., Any], /, *, precedence: int = 0
    ) -> Self:
        """Register `method` by `precedence` and return the function itself.

        Registration path for :meth:`dispatch`. A bound method so the decorator form
        can be built with :func:`functools.partial` rather than a `self`-capturing
        closure, which `mypyc` cannot compile (mypyc/mypyc#1205).
        """
        self.register(method, precedence=precedence)
        return self

    def _register_multiple(
        self: Self, method: Callable[..., Any], /, *, signatures: list[Signature]
    ) -> Self:
        """Register `method` for every signature and return the function itself.

        Registration path for :meth:`dispatch_multi`. See :meth:`_register_one` for
        why this is a bound method.
        """
        for signature in signatures:
            # `precedence` is derived from each signature, so it is left as `None`.
            self.register(method, signature=signature, precedence=None)
        return self

    def clear_cache(self, reregister: bool = True) -> None:
        """Clear cache.

        Args:
            reregister (bool, optional): Also reregister all methods. Defaults to
                `True`.
        """
        # Serialise against concurrent resolution: the `reregister` branch swaps
        # `_pending`/`_resolved`/`_resolver` in multiple steps. See GitHub issue #274.
        with self._lock:
            self._cache.clear()
            self._invoke_cache.clear()
            self._generation += 1

            if reregister:
                # Add all resolved to pending.
                self._pending.extend(self._resolved)

                # Clear resolved.
                self._resolved = []
                self._resolver = Resolver(
                    self._resolver.function_name,
                    warn_redefinition=self._warn_redefinition,
                )

    def register(
        self,
        f: Callable[..., Any],
        signature: Signature | None = None,
        precedence: int | None = 0,
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
        self._pending.append((f, signature, precedence))

    def _resolve_pending_registrations(self) -> None:
        # Fast path: nothing pending. This unlocked check keeps the common
        # already-resolved case, which is the hot dispatch path, lock-free.
        if not self._pending:
            return

        # Resolution mutates each registered function's annotations in place and is not
        # thread-safe, so serialise it. See GitHub issue #274.
        with self._lock:
            # Re-check under the lock: another thread may have completed the resolution
            # while we were waiting to acquire it.
            if not self._pending:
                return

            # Keep track of whether anything registered.
            registered = False

            # Perform any pending registrations.
            for f, signature, precedence in self._pending:
                # Add to resolved registrations.
                self._resolved.append((f, signature, precedence))

                # Obtain the signature if it is not available.
                if signature is None:
                    # When signature is `None`, precedence should always be set.
                    assert precedence is not None
                    signature = Signature.from_callable(f, precedence=precedence)
                else:
                    # Ensure that the implementation is `f`, but make a copy before
                    # mutating.
                    signature = copy(signature)

                # Process default values.
                for subsignature in append_default_args(signature, f):
                    submethod = Method(f, subsignature, function_name=self.__name__)
                    self._resolver.register(submethod)
                    registered = True

            if registered:
                self._pending = []

                # Clear cache. Reenters `self._lock`, which is why it is an `RLock`.
                self.clear_cache(reregister=False)

    def resolve_method(
        self, target: tuple[object, ...] | Signature
    ) -> tuple[Callable[..., Any], TypeHint]:
        """Find the method and return type for arguments.

        Args:
            target (object): Target.

        Returns:
            `tuple[function, type]`:
                * Method.
                * Return type.
        """
        self._resolve_pending_registrations()

        try:
            # Attempt to find the method using the resolver.
            method = self._resolver.resolve(target)
            impl = method.implementation
            return_type = method.return_type

        # The two `except` clauses use distinct variable names (`e_ambiguous` /
        # `e_not_found`) rather than a shared `e`: `mypyc` gives a reused exception
        # variable a single type, so binding the second exception type to it fails a
        # runtime type check.
        except AmbiguousLookupError as e_ambiguous:
            __tracebackhide__ = True

            # Change the function name if this is a method.
            if self.owner:
                e_ambiguous.f_name = self.__qualname__
            raise e_ambiguous from None

        except NotFoundLookupError as e_not_found:
            __tracebackhide__ = True

            # Change the function name if this is a method.
            if self.owner:
                e_not_found.f_name = self.__qualname__
            impl, return_type = self._handle_not_found_lookup_error(e_not_found)

        return impl, return_type

    def _handle_not_found_lookup_error(
        self, ex: NotFoundLookupError, /
    ) -> tuple[Callable[..., Any], TypeHint]:
        if not self.owner:
            # Not in a class. Nothing we can do.
            raise ex from None

        # In a class. Walk through the classes in the class's MRO, except for this
        # class, and try to get the method.
        method: Callable[..., Any] | None = None
        return_type: TypeHint = object

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
            raise ex from None
        return method, return_type

    def __call__(self, *args: object, **kw: object) -> object:
        __tracebackhide__ = True
        method, return_type = self._resolve_method_with_cache(args=args)
        return _convert(method(*args, **kw), return_type)

    def _resolve_method_with_cache(
        self,
        args: tuple[object, ...] | Signature | None = None,
        types: tuple[TypeHint, ...] | None = None,
    ) -> tuple[Callable[..., Any], TypeHint]:
        if args is None and types is None:
            raise ValueError(
                "Arguments `args` and `types` cannot both be `None`. "
                "This should never happen!"
            )

        # Before attempting to use the cache, resolve any unresolved registrations. Use
        # an `if`-statement to speed up the common case.
        if self._pending:
            self._resolve_pending_registrations()

        # Compute cache key. When called from `__call__`, types will be actual
        # runtime types from `map(type, args)`. When called from `invoke`, types
        # may be `TypeHints` like `Union[int, str]`. Both are hashable and work
        # as cache keys.
        if types is None:
            # Attempt to use the cache based on the types of the arguments.
            # At this point, `args` must be a tuple (not `Signature` or `None`).
            assert isinstance(args, tuple)
            types = tuple(map(type, args))
        try:
            return self._cache[types]
        except KeyError:
            __tracebackhide__ = True

            if args is None:
                args = Signature(*(resolve_type_hint(t) for t in types))

            # Cache miss. Read the generation before resolving: `clear_cache` bumps
            # it under the lock, so if it has moved by the time the answer is ready,
            # a registration landed in between and storing would pin a stale method.
            generation = self._generation
            method, return_type = self.resolve_method(args)
            # If the resolver is faithful, then we can perform caching using the types
            # of the arguments. If the resolver is not faithful, then we cannot. And
            # only if no `clear_cache` has run since the generation was read: this
            # store is outside the lock, so without the check a resolution begun
            # before a registration could overwrite the cleared entry afterwards, and
            # nothing would ever invalidate it again.
            if self._resolver.is_faithful and generation == self._generation:
                self._cache[types] = method, return_type
            return method, return_type

    def invoke(self, *types: TypeHint) -> Callable[..., Any]:
        """Invoke a particular method.

        Repeated calls with the same `types` return the identical wrapper, until
        :meth:`clear_cache`.

        Args:
            *types: Types to resolve.

        Returns:
            function: Method.
        """
        # As in `_resolve_method_with_cache`, resolve pending registrations before
        # consulting the cache, or a method registered since the last call is missed.
        if self._pending:
            self._resolve_pending_registrations()

        try:
            return self._invoke_cache[types]
        except KeyError:
            # Read the generation *before* resolving: `clear_cache` bumps it under the
            # lock, so if it has moved by the time the wrapper is built, a registration
            # landed in between and this result is already stale. Storing it anyway
            # would pin it for good -- `_pending` is empty by then, so every later call
            # would hit it and `invoke` would permanently disagree with `__call__`.
            generation = self._generation
            method, return_type = self._resolve_method_with_cache(types=types)
            invoked = _InvokedMethod(self._f, method, return_type)
            # Unlike `_cache`, this is not gated on `is_faithful`: `types` are explicit
            # hints, so resolution does not depend on any runtime value. It is bounded
            # instead; see `_INVOKE_CACHE_LIMIT`.
            if (
                generation == self._generation
                and len(self._invoke_cache) < _INVOKE_CACHE_LIMIT
            ):
                self._invoke_cache[types] = invoked
            return invoked

    @overload
    def __get__(self, instance: None, owner: type, /) -> "Function": ...
    @overload
    def __get__(self, instance: object, owner: type, /) -> MethodType: ...

    def __get__(
        self, instance: object | None, owner: type, /
    ) -> "Function | MethodType":
        if instance is None:
            return self
        return MethodType(_BoundFunction(self, instance), instance)

    def __repr__(self) -> str:
        return (
            f"<multiple-dispatch function {self.__qualname__} (with"
            f" {len(self._resolver)} registered and {len(self._pending)}"
            f" pending method(s))>"
        )


# Attach `__doc__`/`__module__` here, not in the class body: `mypyc` replaces a class
# `__doc__` with a filler, and `__module__` is read-only on a native instance. These
# descriptors serve instance access (`f.__doc__`, `f.__module__`). `setattr` also stops
# `mypy` treating these as class variables.
setattr(Function, "__doc__", _DocDescriptor())  # noqa: B010
setattr(Function, "__module__", _ModuleDescriptor(__name__))  # noqa: B010


def _generate_qualname(f: Callable[..., Any], /) -> str:
    """Generate a qualified name for a function.

    This function can be interpreted as an improved version of `f.__qualname__`
    and can be run regardless of whether `f.__qualname__` exists.

    Args:
        f (Callable): Function.

    Returns:
        str: Qualified name.
    """
    qualname = getattr(f, "__qualname__", f.__name__)

    # TODO: If we ever want to scope functions, we can uncomment this.
    # if hasattr(f, "__module__"):
    #     qualname = f"{f.__module__}.{qualname}"
    # `__main__` would be part of `f.__name__` in e.g. the REPL.
    # qualname = qualname.replace("__main__.", """)

    return qualname


class _DispatchFunction(Protocol):
    """Protocol for the `dispatch` method of a function."""

    def __call__(
        self, method: Callable[..., Any] | None, precedence: int
    ) -> Self | Callable[[Callable[..., Any]], Self]: ...


class _BoundFunctionProto(Protocol):
    """Subset of :class:`Function`'s interface required by :class:`_BoundFunction`.

    Declaring `_BoundFunction._f` with this Protocol rather than :class:`Function`
    directly prevents `mypy` from applying `Function.__get__`'s descriptor protocol
    when resolving instance-attribute accesses of `_f`.
    """

    _f: Callable[..., Any]

    def __call__(self, *args: object, **kw: object) -> object: ...

    def invoke(self, *types: TypeHint) -> Callable[..., Any]: ...

    @property
    def methods(self) -> MethodList: ...

    def dispatch(
        self,
        method: Callable[..., Any] | None = None,
        precedence: int = 0,
    ) -> Any: ...


class _BoundFunction:
    #: The class-level docstring, served as `_BoundFunction.__doc__` by
    #: `_DocDescriptor`.
    _class_doc: ClassVar[str] = """A bound instance of `.function.Function`.

    Args:
        f (:class:`.function.Function`): Bound function.
        instance (object): Instance to which the function is bound.
    """

    # Declared so `_BoundFunction` is a `mypyc` native class (like `Function`), which
    # speeds up bound (class-method) dispatch. `_f` holds a `Function` (typed as proto);
    # the dunders are also what `_wraps_native` writes (see `_NativeWrappable`).
    _f: _BoundFunctionProto
    _instance: object
    __name__: str
    __qualname__: str
    __wrapped__: Callable[..., Any]

    def __init__(self, f: "Function", instance: object) -> None:
        self._f = f
        self._instance = instance
        # Wrap the underlying function `f._f`, like `Function`. `__doc__`/`__module__`
        # are served by the descriptors attached below.
        _wraps_native(self, f._f)

    def _compute_doc(self) -> str | None:
        return self._f.__doc__

    def __call__(self, _: object, *args: object, **kw: object) -> object:
        return self._f(self._instance, *args, **kw)

    def invoke(self, *types: TypeHint) -> Callable[..., Any]:
        """See :meth:`.Function.invoke`."""
        # Unlike `Function.invoke`, `_BoundInvokedMethod` sets no `__wrapped_by_plum__`:
        # it prepends `self._instance`, so there is no extendable method to unwrap to.
        return _BoundInvokedMethod(self, types)

    @property
    def methods(self) -> MethodList:
        """list[:class:`.method.Method`]: All available methods."""
        return self._f.methods

    @property
    def dispatch(self) -> _DispatchFunction:
        """See :meth:`.Function.dispatch`."""
        return self._f.dispatch


# See `Function` above: the descriptors serve `__doc__`/`__module__` on instances.
setattr(_BoundFunction, "__doc__", _DocDescriptor())  # noqa: B010
setattr(_BoundFunction, "__module__", _ModuleDescriptor(__name__))  # noqa: B010


@mypyc_attr(native_class=False)
class _BoundInvokedMethod:
    """Callable returned by :meth:`_BoundFunction.invoke` (see there)."""

    def __init__(self, bound: "_BoundFunction", types: tuple[TypeHint, ...]) -> None:
        self._bound = bound
        self._types = types
        # `bound.__wrapped__` is the underlying function (`f._f`), set in
        # `_BoundFunction.__init__`.
        _wraps(self, bound.__wrapped__)

    def __call__(self, *args: Any, **kw: Any) -> Any:
        # TODO: Can we do this without `type` here?
        method = self._bound._f.invoke(type(self._bound._instance), *self._types)
        return method(self._bound._instance, *args, **kw)
