__all__ = ("Function",)

import os
import textwrap
import threading
import weakref
from collections.abc import Callable
from copy import copy
from functools import wraps
from types import MethodType
from typing import Any, Protocol, TypeAlias, TypeVar, overload

from beartype.typing import Protocol
from typing_extensions import Self

from ._bear import is_bearable_with_orig
from ._method import Method, MethodList
from ._resolver import AmbiguousLookupError, NotFoundLookupError, Resolver
from ._signature import Signature, append_default_args
from ._type import resolve_type_hint
from ._util import TypeHint

_promised_convert = None
"""function or None: This will be set to :func:`.parametric.convert`."""

SomeExceptionType = TypeVar("SomeExceptionType", bound=Exception)
TypeHints: TypeAlias = tuple[TypeHint, ...]
CallAny: TypeAlias = Callable[..., Any]
FunctionCacheEntry: TypeAlias = tuple[CallAny, TypeHint]


def _arg_key(arg: object, /) -> object:
    """Return the effective cache key for a single dispatch argument.

    For instances produced via subscripted-generic instantiation (e.g.
    ``Box[int](1)``) Python sets ``instance.__orig_class__ = Box[int]`` after
    ``__init__`` returns.  Using the subscripted form as the cache key ensures
    that ``Box[int](1)`` and ``Box[str]('x')`` land in separate buckets and are
    matched with :func:`._bear.is_bearable_with_orig` rather than the bare-type
    fallback path.

    For all other values the bare ``type(arg)`` is returned unchanged.
    """
    orig = getattr(arg, "__orig_class__", None)
    # ``__orig_class__`` is set by Python after subscripted instantiation and by
    # the ``@generic`` decorator.  We trust it is correct.
    return orig if orig is not None else type(arg)


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


class _FunctionMeta(type):
    """:class:`Function` implements `__doc__`, which overrides the docstring of the
    class. This simple metaclass ensures that `Function.__doc__` still prints as the
    docstring of the class."""

    _class_doc: str | None

    @property
    def __doc__(self) -> str | None:  # type: ignore[override]
        return self._class_doc


class Function(metaclass=_FunctionMeta):
    """A function.

    Args:
        f (function): Function that is wrapped.
        owner (str, optional): Name of the class that owns the function.
        warn_redefinition (bool, optional): Throw a warning whenever a method is
            redefined. Defaults to `False`.
    """

    # When we set `__doc__`, we will lose the docstring of the class, so we save it now.
    # Correctly printing the docstring is handled by :class:`_FunctionMeta`.
    _class_doc = __doc__

    _instances: weakref.WeakSet["Function"] = weakref.WeakSet()

    def __init__(
        self, f: CallAny, /, owner: str | None = None, warn_redefinition: bool = False
    ) -> None:
        Function._instances.add(self)

        self._f: CallAny = f
        # Cache maps type tuples to `(method, return_type)`. Keys can be either
        # actual types (from `__call__`) or `TypeHints` (from `invoke`).
        self._cache: dict[TypeHints, FunctionCacheEntry]
        self._cache = {}

        # Guards the lazy resolution of pending registrations, which mutates each
        # registered function's `__annotations__` in place (via beartype's
        # `resolve_pep563`) and is otherwise not thread-safe. Reentrant because
        # `_resolve_pending_registrations` calls `clear_cache`, which also acquires this
        # lock. See GitHub issue #274.
        self._lock = threading.RLock()

        # Two-tier cache for generic dispatch.  Keyed on bare runtime types
        # (cheap to compute); each bucket holds a list of
        # (hint_tuple, impl, return_type) candidates verified via is_bearable.
        self._generic_cache: dict[
            tuple[object, ...], list[tuple[tuple[TypeHint, ...], CallAny, TypeHint]]
        ]
        self._generic_cache = {}
        # Keys present in this set have buckets built by pre-population
        # (_resolve_pending_registrations) where all candidate methods are
        # pairwise comparable and sorted most-specific-first.  For those keys
        # the first is_bearable_with_orig match is the most specific answer;
        # no second-match scan is needed.
        self._generic_cache_sorted: set[tuple[object, ...]] = set()
        wraps(f)(self)  # Sets `self._doc`.

        self.__name__ = f.__name__
        self.__qualname__ = _generate_qualname(f)

        # `owner` is the name of the owner. We will later attempt to resolve to
        # which class it actually points.
        self._owner_name: str | None = owner
        self._owner: type | None = None

        self._warn_redefinition = warn_redefinition

        # Initialise pending and resolved methods.
        self._pending: list[tuple[CallAny, Signature | None, int | None]] = []
        self._resolver = Resolver(
            self.__name__,
            warn_redefinition=self._warn_redefinition,
        )
        self._resolved: list[tuple[CallAny, Signature | None, int | None]] = []

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

    @property
    def __doc__(self) -> str | None:
        """str or None: Documentation of the function. This consists of the
        documentation of the function given at initialisation with the documentation
        of all other registered methods appended.

        Upon instantiation, this property is available through `obj.__doc__`.
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

    @__doc__.setter
    def __doc__(self, value: str | None, /) -> None:
        # Ensure that `self._doc` remains a string.
        self._doc = value if value else ""

    @property
    def methods(self) -> MethodList:
        """list[:class:`.method.Method`]: All available methods."""
        self._resolve_pending_registrations()
        return self._resolver.methods

    def dispatch(
        self: Self, method: CallAny | None = None, precedence: int = 0
    ) -> Self | Callable[[CallAny], Self]:
        """Decorator to extend the function with another signature.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to `0`.

        Returns:
            function: Decorator.
        """
        if method is None:
            return lambda m: self.dispatch(m, precedence=precedence)  # type: ignore[return-value]

        self.register(method, precedence=precedence)
        return self

    def dispatch_multi(
        self: Self, *signatures: Signature | TypeHints
    ) -> Callable[[CallAny], Self]:
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

        def decorator(method: CallAny, /) -> "Function":
            # The precedence will not be used, so we can safely set it to `None`.
            for signature in resolved_signatures:
                self.register(method, signature=signature, precedence=None)
            return self

        return decorator  # type: ignore[return-value]

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
            self._generic_cache.clear()
            self._generic_cache_sorted.clear()

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
        f: CallAny,
        /,
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

                # Eagerly pre-populate _generic_cache for arity-1 generic functions
                # as a best-effort fast path.  This lets the first dispatch avoid
                # the resolver when the runtime cache key matches the generic origin
                # (e.g. builtins and custom generics where type(arg) is the origin
                # directly).  For ABC generics such as Sequence the runtime key is
                # type(arg) — e.g. (list,) — which differs from the origin key
                # (collections.abc.Sequence,), so those calls still miss the cache
                # and fall through to resolution.  Skip origins where any two
                # methods are incomparable — those origins could yield
                # AmbiguousLookupError for some inputs (e.g. list[int] vs list[str]
                # for an empty list), and must fall through to the resolver.
                for origin, methods in self._resolver._arity1_methods.items():
                    if any(
                        not m1.signature.is_comparable(m2.signature)
                        for i, m1 in enumerate(methods)
                        for m2 in methods[i + 1 :]
                    ):
                        continue
                    self._generic_cache[(origin,)] = [
                        (m.signature.types, m.implementation, m.return_type)
                        for m in methods
                    ]
                    self._generic_cache_sorted.add((origin,))

    def resolve_method(
        self, target: tuple[object, ...] | Signature, /
    ) -> FunctionCacheEntry:
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

        except AmbiguousLookupError as e:
            __tracebackhide__ = True

            # Change the function name if this is a method.
            if self.owner:
                e.f_name = self.__qualname__
            raise e from None

        except NotFoundLookupError as e:
            __tracebackhide__ = True

            # Change the function name if this is a method.
            if self.owner:
                e.f_name = self.__qualname__
            impl, return_type = self._handle_not_found_lookup_error(e)

        return impl, return_type

    def _handle_not_found_lookup_error(
        self, ex: NotFoundLookupError, /
    ) -> FunctionCacheEntry:
        if not self.owner:
            # Not in a class. Nothing we can do.
            raise ex from None

        # In a class. Walk through the classes in the class's MRO, except for
        # this class, and try to get the method.
        method: CallAny | None = None
        return_type: TypeHint = object

        for c in self.owner.__mro__[1:]:
            # Skip the top of the type hierarchy given by `object` and `type`.
            # We do not suddenly want to fall back to any unexpected default
            # behaviour.
            if c in {object, type}:
                continue

            # We need to check `c.__dict__` here instead of using `hasattr`
            # since e.g.  `c.__le__` will return  even if `c` does not implement
            # `__le__`!
            if self._f.__name__ in c.__dict__:
                method = getattr(c, self._f.__name__)
            else:
                # For some reason, coverage fails to catch the `continue` below.
                # Add the do-nothing `_ = None` fixes this.
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

    def _resolve_generic(self, args: tuple[object, ...]) -> FunctionCacheEntry:
        # Build the cache key using __orig_class__ when available (custom
        # generics like Box[int](1)) or the bare runtime type otherwise (stdlib
        # generics like list, dict).  This ensures Box[int] and Box[str] land in
        # separate buckets while two plain `list` args share the same key
        # `(list, list)`.
        key = tuple(map(_arg_key, args))

        # --- Fast path: cache hit ---
        # Scan stored candidates for is_bearable_with_orig matches.
        #
        # Two cases:
        #   _presorted (key in _generic_cache_sorted): the bucket was built by
        #     pre-population with all pairwise-comparable methods sorted
        #     most-specific-first.  The first match is the definitive answer;
        #     break immediately (original O(1) behaviour).
        #   unsorted (dynamically accumulated via slow-path appends): methods may
        #     be incomparable (e.g. list[int] vs list[str]).  We must check for a
        #     second match before returning — if one exists the call is ambiguous
        #     (or needs most-specific resolution) and must fall through to the
        #     resolver.  Returning the first match silently would be wrong when
        #     both list[int] and list[str] vacuously match an empty list.
        candidates = self._generic_cache.get(key)
        if candidates is not None:
            _presorted = key in self._generic_cache_sorted
            _first_impl: CallAny | None = None
            _first_rt: TypeHint | None = None
            _ambiguous = False
            for hint_tuple, impl, return_type in candidates:
                if all(
                    is_bearable_with_orig(a, h)
                    for a, h in zip(args, hint_tuple, strict=False)
                ):
                    if _first_impl is None:
                        _first_impl, _first_rt = impl, return_type
                        if _presorted:
                            # Bucket was built most-specific-first from comparable
                            # methods only; the first match is the definitive answer.
                            break
                    else:
                        # Second match in an unsorted bucket: ambiguous or needs
                        # most-specific resolution — fall through to the resolver.
                        _ambiguous = True
                        break
            if _first_impl is not None and not _ambiguous:
                # Exactly one candidate matched — fast return.
                return _first_impl, _first_rt
            # Zero or multiple matches: fall through to the resolver for the
            # authoritative answer (raises AmbiguousLookupError if ambiguous,
            # or selects the most-specific candidate).

        # --- Slow path: full resolver ---
        # No cached candidate matched.  Delegate to the resolver for the
        # authoritative answer.  For single-argument functions we can skip the
        # general resolver and use the pre-filtered _arity1_methods map, which
        # only contains methods whose origin matches this argument's type.
        try:
            if len(args) == 1 and self._resolver._arity1_methods:
                resolved = self._resolver.resolve_for_type(args, key[0])
            else:
                resolved = self._resolver.resolve(args)
        except AmbiguousLookupError as e:
            __tracebackhide__ = True
            if self.owner:
                e.f_name = self.__qualname__
            raise e from None
        except NotFoundLookupError as e:
            __tracebackhide__ = True
            if self.owner:
                e.f_name = self.__qualname__
            return self._handle_not_found_lookup_error(e)

        impl = resolved.implementation
        return_type = resolved.return_type
        sig = resolved.signature

        # Build the hint tuple to store in the cache.  For vararg signatures the
        # tuple must be extended to cover any extra positional arguments so that
        # is_bearable_with_orig is called on every arg on future cache hits.
        if sig.has_varargs:
            n_extra = len(args) - len(sig.types)
            hint_tuple = sig.types + (sig.varargs,) * max(0, n_extra)
        else:
            hint_tuple = sig.types

        entry = (hint_tuple, impl, return_type)

        # Populate the cache.  If this key was seen before but no candidate
        # matched (all candidates failed is_bearable_with_orig), append the new
        # entry so subsequent calls with the same key try it.  If the key is
        # brand new, create the bucket with this single entry.
        if candidates is None:
            self._generic_cache[key] = [entry]
        else:
            # Deduplicate: avoid appending an entry whose implementation is already
            # present.  Without this guard, repeated falls-through to the resolver
            # (e.g. for f([]) when both list[int] and list match) would grow the
            # bucket without bound.
            if not any(existing_impl is impl for _, existing_impl, _ in candidates):
                candidates.append(entry)

        return impl, return_type

    def _resolve_method_with_cache(
        self,
        args: tuple[object, ...] | Signature | None = None,
        types: TypeHints | None = None,
    ) -> FunctionCacheEntry:
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
            # Compute the bare-type tuple once; it is reused for both the
            # needs_generic check below and as the cache key.
            types = tuple(map(type, args))
            if self._resolver.has_generic_signatures:
                # Check whether any argument's runtime type overlaps with a
                # registered generic origin (e.g. list for list[int]).
                needs_generic = any(
                    issubclass(t, o)
                    for t in types
                    for o in self._resolver.generic_origins
                )
                if needs_generic:
                    return self._resolve_generic(args)
        try:
            return self._cache[types]
        except KeyError:
            __tracebackhide__ = True

            if args is None:
                args = Signature(*(resolve_type_hint(t) for t in types))

            # Cache miss. Run the resolver based on the arguments.
            method, return_type = self.resolve_method(args)
            # Cache by bare type when it is safe to do so:
            #   1. All methods are faithful (resolver-wide), OR
            #   2. We're on the non-generic arm of a mixed function and every
            #      non-generic method is faithful (i.e. no value-dependent overloads
            #      like Annotated/BeartypeValidator).  Generic-only methods can never
            #      be reached on this arm, so they don't affect caching safety.
            if self._resolver.is_faithful or (
                self._resolver.has_generic_signatures
                and self._resolver.is_faithful_for_non_generic
            ):
                self._cache[types] = method, return_type
            return method, return_type

    def invoke(self, *types: TypeHint) -> CallAny:
        """Invoke a particular method.

        Args:
            *types: Types to resolve.

        Returns:
            function: Method.
        """
        method, return_type = self._resolve_method_with_cache(types=types)

        @wraps(self._f)
        def wrapped_method(*args: Any, **kw: Any) -> Any:
            return _convert(method(*args, **kw), return_type)

        wrapped_method.__wrapped_by_plum__ = method  # type: ignore[attr-defined]

        return wrapped_method

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


def _generate_qualname(f: CallAny, /) -> str:
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


class _DispatchFunction(Protocol):  # type: ignore[misc]
    """Protocol for the `dispatch` method of a function."""

    def __call__(  # type: ignore[empty-body]
        self, method: CallAny | None, precedence: int
    ) -> Self | Callable[[CallAny], Self]: ...


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
    """A bound instance of `.function.Function`.

    Args:
        f (:class:`.function.Function`): Bound function.
        instance (object): Instance to which the function is bound.
    """

    _f: "_BoundFunctionProto"
    _instance: object

    def __init__(self, f: "Function", instance: object, /) -> None:
        self._f = f
        wraps(f._f)(self)  # This will call the setter for `__doc__`.
        self._instance = instance

    @property
    def __doc__(self) -> str | None:
        return self._f.__doc__

    @__doc__.setter
    def __doc__(self, value: str | None, /) -> None:
        # Don't need to do anything here. The docstring will be derived from `self._f`.
        # We, however, do need to implement this method, because :func:`wraps` calls
        # it.
        pass

    def __call__(self, _: object, /, *args: object, **kw: object) -> object:
        return self._f(self._instance, *args, **kw)

    def invoke(self, *types: TypeHint) -> CallAny:
        """See :meth:`.Function.invoke`."""

        @wraps(self._f._f)
        def wrapped_method(*args: Any, **kw: Any) -> Any:
            # TODO: Can we do this without `type` here?
            method = self._f.invoke(type(self._instance), *types)
            return method(self._instance, *args, **kw)

        # We set `f.__wrapped_by_plum__` for :func:`Function.invoke`, but here
        # we do not: this method has `self._instance` prepended to its
        # arguments, so there is no "wrapped method". In addition, bound
        # functions cannot be directly extended, so unwrapping is likely never
        # desired.

        return wrapped_method

    @property
    def methods(self) -> MethodList:
        """list[:class:`.method.Method`]: All available methods."""
        return self._f.methods

    @property
    def dispatch(self) -> _DispatchFunction:
        """See :meth:`.Function.dispatch`."""
        return self._f.dispatch
