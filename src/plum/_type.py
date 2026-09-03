__all__ = (
    "PromisedType",
    "ModuleType",
    "type_mapping",
    "resolve_type_hint",
    "is_faithful",
    "is_cacheable",
    "cache_key",
    "KeyPart",
    "CacheSpec",
)

import abc
import enum
import itertools
import sys
import typing
import warnings
from collections.abc import Callable, Hashable, Iterable
from functools import lru_cache, reduce
from operator import or_
from types import GenericAlias, UnionType
from typing import (
    Any,
    Literal,
    TypeGuard,
    TypeVar,
    cast,
    final,
    get_args,
    get_origin,
)

from beartype.door import TypeHint as TypeHintWrapper
from beartype.vale._core._valecore import BeartypeValidator

from ._mypyc import mypyc_attr

T = TypeVar("T", bound="ResolvableType")


@mypyc_attr(native_class=False)
class ResolvableType(type):
    """A resolvable type that will resolve to `type` after `type` has been delivered via
    :meth:`.ResolvableType.deliver`. Before then, it will resolve to itself.

    Args:
        name (str): Name of the type to be delivered.
    """

    def __init__(self, name: str, /) -> None:
        type.__init__(self, name, (), {})
        self._type: type | None = None

    def __new__(cls: type[T], name: str) -> T:
        return type.__new__(cls, name, (), {})

    def deliver(self: T, delivered_type: type, /) -> T:
        """Deliver the type.

        Args:
            delivered_type (type): Type to deliver.

        Returns:
            :class:`ResolvableType`: `self`.
        """
        self._type = delivered_type
        return self

    def resolve(self: T) -> type | T:
        """Resolve the type.

        Returns:
            type: If no type has been delivered, this will return itself. If a type
                `type` has been delivered via :meth:`.ResolvableType.deliver`, this will
                return that type.
        """
        return self if self._type is None else self._type


@final
@mypyc_attr(native_class=False)
class PromisedType(ResolvableType):
    """A type that is promised to be available when you will you need it.

    Args:
        name (str, optional): Name of the type that is promised. Defaults to
            `"SomeType"`.
    """

    def __init__(self, name: str = "SomeType") -> None:
        ResolvableType.__init__(self, f"PromisedType[{name}]")
        self._name = name

    def __new__(cls, name: str = "SomeType") -> "PromisedType":
        # `ResolvableType.__new__` rather than `super().__new__` so `mypyc` can compile
        # this (it cannot generate `object.__new__` for a non-extension class).
        return ResolvableType.__new__(cls, f"PromisedType[{name}]")

    def __repr__(self) -> str:
        return f"<class 'plum.PromisedType[{self._name}]'>"


TModuleType = TypeVar("TModuleType", bound="ModuleType")


@final
@mypyc_attr(native_class=False)
class ModuleType(ResolvableType):
    """A type from another module.

    Args:
        module (str): Module that the type lives in.
        name (str): Name of the type that is promised.
        allow_fail (bool, optional): If the type is does not exist in `module`,
            do not raise an `AttributeError`.
        condition (Callable[[], bool], optional): A callable that can check a condition,
            like a package version. This callable will be run whenever `module` has been
            imported. Only if the callable returns `True`, `name` will be imported
            from `module`.
        faithful (bool, optional): If set, set the dunder `__faithful__` of the type to
            this value upon retrieval.
    """

    def __init__(
        self,
        module: str,
        name: str,
        *,
        allow_fail: bool = False,
        condition: Callable[[], bool] | None = None,
        faithful: bool | None = None,
    ) -> None:
        if module in {"__builtin__", "__builtins__"}:
            module = "builtins"
        super().__init__(f"ModuleType[{module}.{name}]")
        self._name = name
        self._module = module
        self._allow_fail = allow_fail
        self._condition = condition
        self._faithful = faithful

    def __new__(
        cls: type[TModuleType], module: str, name: str, **kwargs: object
    ) -> TModuleType:
        return ResolvableType.__new__(cls, f"ModuleType[{module}.{name}]")

    def deliver(self: TModuleType, delivered_type: type, /) -> TModuleType:
        return_value = super().deliver(delivered_type)
        if self._faithful is not None:
            # Only set `delivered_type.__faithful__` if it is not already set to a
            # different value.
            if (
                # Use `hasattr` instead of `_has_dunder_faithful` so `mypy` remains
                # aware that `delivered_type` is a `type` and won't complain about
                # `delivered_type.__name__`.
                hasattr(delivered_type, "__faithful__")
                and delivered_type.__faithful__ != self._faithful
            ):
                raise TypeError(
                    f"`{delivered_type.__name__}.__faithful__` is already set and "
                    f"would be changed by `{self.__name__}` to a different value."
                )
            delivered_type.__faithful__ = self._faithful  # type: ignore[attr-defined]
        return return_value

    def retrieve(self) -> bool:
        """Attempt to retrieve the type from the reference module.

        Returns:
            bool: Whether the retrieval succeeded.
        """
        if self._type is None and self._module in sys.modules:
            # If a condition is given, check the condition before attempting to import.
            if self._condition is not None and not self._condition():
                return False

            retrieved: object = sys.modules[self._module]
            for name in self._name.split("."):
                # If `retrieved` does not contain `name` and `self._allow_fail` is
                # set, then silently fail.
                if not hasattr(retrieved, name) and self._allow_fail:
                    return False
                retrieved = getattr(retrieved, name)
            # We expect this to be a type, so we cast it.
            self.deliver(cast(type, retrieved))
        return self._type is not None


def _is_hint(x: object) -> bool:
    """Check if an object is a type hint.

    Args:
        x (object): Object.

    Returns:
        bool: `True` if `x` is a type hint and `False` otherwise.
    """
    try:
        if x.__module__ == "builtins" and type(x) is GenericAlias:
            # `x` is a subscripted built-in, e.g. `list[int]`, so check the module of
            # its type instead. A class declared with `exec`, e.g. in a doctest, also
            # has `__module__ == "builtins"`, hence the check on `type(x)`.
            x = type(x)
        return x.__module__ in {
            "types",  # E.g., `tuple[int]`
            "typing",
            "collections.abc",  # E.g., `Callable`
            "typing_extensions",
        }
    except AttributeError:
        return False


def _hashable(x: object | type) -> TypeGuard[Hashable]:
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


type_mapping: dict[type, type] = {}
"""dict: When running :func:`resolve_type_hint`, map keys in this dictionary to the
values."""


def resolve_type_hint(x: object, /) -> object:
    """Resolve all :class:`ResolvableType` in a type or type hint.

    Args:
        x (type or type hint): Type hint.

    Returns:
        type or type hint: `x`, but with all :class:`ResolvableType`\\s resolved.
    """
    if _hashable(x) and isinstance(x, type) and x in type_mapping:
        return resolve_type_hint(type_mapping[x])
    elif _is_hint(x):
        origin = get_origin(x)
        args = get_args(x)
        if args == ():
            # `origin` might not make sense here. For example, `get_origin(Any)`
            # is `None`. Since the hint wasn't subscripted, the right thing is
            # to return the hint itself.
            return x
        if origin is UnionType:  # The new union syntax was used.
            return reduce(or_, (resolve_type_hint(arg) for arg in args))
        else:
            # Do not resolve the arguments for `Literal`s.
            if origin is not Literal:
                resolved_args = resolve_type_hint(args)
                assert isinstance(resolved_args, tuple)
                args = resolved_args

            # Ensure origin is not `None` before indexing.
            assert origin is not None
            return origin[args]

    elif x is None or x is Ellipsis:
        return x

    elif isinstance(x, tuple):
        return tuple(resolve_type_hint(arg) for arg in x)
    elif isinstance(x, list):
        return [resolve_type_hint(arg) for arg in x]
    elif isinstance(x, type):
        if not isinstance(x, ResolvableType):
            return x
        elif isinstance(x, ModuleType) and not x.retrieve():
            # If the type could not be retrieved, then just return the
            # wrapper. Namely, `x.resolve()` will then return `x`, which
            # means that the below call will result in an infinite
            # recursion.
            return x

        return resolve_type_hint(x.resolve())

    # For example, `Is[lambda x: x > 0]` is an example of a `BeartypeValidator`.
    # We shouldn't resolve those.
    elif isinstance(x, BeartypeValidator):
        return x

    else:
        warnings.warn(
            f"Could not resolve the type hint of `{x}`. "
            f"I have ended the resolution here to not make your code break, but some "
            f"types might not be working correctly. "
            f"Please open an issue at https://github.com/beartype/plum.",
            stacklevel=2,
        )
    return x


def _substitute_any(hint: object, /) -> object:
    """Replace every `Any` in `hint` with `object`.

    For Plum's signature bookkeeping, `object` has exactly the ordering that `Any`
    should have: it is a subhint of nothing but itself, and everything is a subhint
    of it. Rewriting `Any` to `object` therefore leaves nesting and variance to
    `beartype`. A hint that cannot be rebuilt is returned unchanged.

    Args:
        hint (object): Already-resolved type hint.

    Returns:
        object: `hint` with every `Any` replaced by `object`.
    """
    if hint is Any:
        return object
    if isinstance(hint, list):
        # The parameters of a `Callable`.
        return [_substitute_any(arg) for arg in hint]
    origin = get_origin(hint)
    # `Literal`'s arguments are values, not hints, so they must not be rewritten.
    if origin is None or origin is Literal:
        return hint
    args = get_args(hint)
    new_args = tuple(_substitute_any(arg) for arg in args)
    if new_args == args:
        return hint
    try:
        if origin is UnionType:
            # `types.UnionType` cannot be subscripted.
            return reduce(or_, new_args)
        return origin[new_args]
    except Exception:
        return hint


class _OpaqueHint:
    """Fallback for a hint `beartype.door.TypeHint` refuses to wrap, e.g. a Sphinx
    `autodoc_mock_imports` placeholder. Compares equal only to another opaque
    wrapper around an equal hint, and is a subhint of nothing else. See GitHub
    discussion #298.

    Args:
        hint (object): Hint that `beartype.door.TypeHint` cannot wrap.
    """

    def __init__(self, hint: object, /) -> None:
        self._hint = hint

    def __eq__(self, other: object, /) -> bool:
        return isinstance(other, _OpaqueHint) and self._hint == other._hint

    def __le__(self, other: object, /) -> bool:
        return self == other

    # `beartype.door.TypeHint.__le__` returns `NotImplemented` for a non-`TypeHint`
    # operand rather than raising, so `TypeHintWrapper(...) <= _OpaqueHint(...)` falls
    # back to this reflected method; without it, Python raises `TypeError`.
    def __ge__(self, other: object, /) -> bool:
        return self == other


def _wrap_type_hint_uncached(hint: object, /) -> TypeHintWrapper | _OpaqueHint:
    try:
        return TypeHintWrapper(_substitute_any(hint))
    except Exception:
        warnings.warn(
            f"Could not wrap the type hint `{hint}` for comparison. "
            f"I have fallen back to comparing it for equality only, so methods with "
            f"this type hint might not be ordered correctly. "
            f"Please open an issue at https://github.com/beartype/plum.",
            stacklevel=2,
        )
        return _OpaqueHint(hint)


_wrap_type_hint_cached = lru_cache(maxsize=4096)(_wrap_type_hint_uncached)


def _wrap_type_hint(hint: object, /) -> TypeHintWrapper | _OpaqueHint:
    """Wrap `hint` for comparison, replacing every `Any` by `object`.

    `Signature` comparison wraps the same fixed hints on every uncached dispatch, so
    the rewrite and `beartype`'s own wrapper lookup would otherwise repeat per call.

    Args:
        hint (object): Already-resolved type hint.

    Returns:
        TypeHintWrapper | _OpaqueHint: Wrapped hint, or an `_OpaqueHint` if `beartype`
            cannot wrap `hint`.
    """
    # The same hints are compared over and over, so cache the wrapper. Not every hint
    # is hashable, e.g. `Annotated[int, {"a": 1}]`, so only cache when possible.
    try:
        return _wrap_type_hint_cached(hint)
    except TypeError:
        # Cannot hash `hint`.
        return _wrap_type_hint_uncached(hint)


def _type_hint_le(x: object, y: object, /) -> bool:
    """Check whether `x` is a subhint of `y`, where `Any` is only a subhint of itself.

    Since `beartype` 0.23, `is_subhint(Any, T)` is `True` for every `T`, which would
    make an unannotated (`Any`-typed) parameter as specific as any concrete type. See
    https://github.com/beartype/plum/issues/295. For Plum's signature bookkeeping, `Any`
    must instead be the unique least specific type. This check therefore differs from
    `beartype.door.TypeHint(x) <= TypeHint(y)` in exactly one respect: a root `Any` is
    only a subhint of `Any`, and a nested `Any` is rewritten to `object` by
    `_substitute_any`, which reproduces `beartype<0.23`.

    The difference is permanent: `beartype` made `Any` a subhint of everything by
    design, see https://github.com/beartype/beartype/pull/616.

    Args:
        x (object): First, already-resolved type hint.
        y (object): Second, already-resolved type hint.

    Returns:
        bool: Whether `x` is a subhint of `y`.
    """
    if x is Any:
        return y is Any
    if y is Any:
        return True
    return bool(_wrap_type_hint(x) <= _wrap_type_hint(y))


def _type_hint_eq(x: object, y: object, /) -> bool:
    """Check whether `x` and `y` are the same hint, where `Any` equals only itself.

    See `_type_hint_le`.

    Args:
        x (object): First, already-resolved type hint.
        y (object): Second, already-resolved type hint.

    Returns:
        bool: Whether `x` and `y` denote the same type.
    """
    # `_substitute_any` maps a root `Any` to `object`, so `Any` must be compared here.
    if x is Any or y is Any:
        return x is y
    # Do not derive this from `_type_hint_le`: `TypeHintWrapper.__eq__` already checks
    # both directions in one pass.
    return bool(_wrap_type_hint(x) == _wrap_type_hint(y))


UNION_TYPES = (typing.Union, UnionType, typing.Optional)


class KeyPart(enum.Enum):
    """Part of a cache key beyond `type(x)` that a non-faithful type may need.

    `IDENTITY` is the class `x` itself, which `type[X]` needs. `VALUE` is the value of
    `x`, which `Literal[...]` needs.
    """

    IDENTITY = "identity"
    VALUE = "value"


CacheSpec = frozenset[KeyPart]
"""type: Parts of the cache key that a type needs, beyond `type(x)`.

The empty set means that the type is faithful. Where a `CacheSpec` is optional, `None`
means that the type is not cacheable.
"""

_CANONICAL_SPECS: dict[CacheSpec, CacheSpec] = {
    frozenset(parts): frozenset(parts)
    for r in range(len(KeyPart) + 1)
    for parts in itertools.combinations(KeyPart, r)
}
"""dict: Every possible `CacheSpec`, mapped to one shared instance of it.

A union of `frozenset`s always allocates a new one, so `_combine` looks the result up
here. Equal specs are then the same object and can be compared with `is`."""

_NO_PARTS: CacheSpec = _CANONICAL_SPECS[frozenset()]
_IDENTITY: CacheSpec = _CANONICAL_SPECS[frozenset({KeyPart.IDENTITY})]
_VALUE: CacheSpec = _CANONICAL_SPECS[frozenset({KeyPart.VALUE})]
_ALL_PARTS: CacheSpec = _CANONICAL_SPECS[frozenset(KeyPart)]


class _SupportsDunderFaithful(typing.Protocol):
    __faithful__: bool


def _has_dunder_faithful(x: type, /) -> TypeGuard[_SupportsDunderFaithful]:
    """Check whether `x` has the `__faithful__` attribute."""
    return hasattr(x, "__faithful__")


class _Identity:
    """Wrap an object so that it hashes by `id` and compares by identity.

    The hash and equality of a class come from its metaclass, which can make distinct
    classes compare equal or make a class unhashable. A value can be unhashable too.
    Holding `obj` ensures that its `id` is not reused while the wrapper exists.

    Args:
        obj (object): Object to wrap.
    """

    __slots__ = ("obj",)

    def __init__(self, obj: object, /) -> None:
        self.obj = obj

    def __hash__(self) -> int:
        return id(self.obj)

    def __eq__(self, other: object, /) -> bool:
        return type(other) is _Identity and self.obj is other.obj


def _identity(x: object, /) -> object | None:
    """Get the `IDENTITY` part of `cache_key(x)`.

    This is `None` if `x` is not a class. A class whose metaclass is `type` already
    hashes by `id` and compares by identity, so it is not wrapped in `_Identity`.
    """
    if not isinstance(x, type):
        return None
    return x if type(x) is type else _Identity(x)


_LITERAL_TYPES: frozenset[type] = frozenset({bool, int, str, bytes, type(None)})
"""The exact types PEP 586 allows a `Literal` to hold; a value of one of these is
keyed by its own value. Instances of *subclasses* also match a `Literal`, and are
keyed differently -- see `_value`."""

_LITERAL_BASES: tuple[type, ...] = (int, str, bytes, enum.Enum)
"""Bases whose instances can also match a `Literal`: an `int` subclass and an
`Enum` member both do. `bool` and `NoneType` cannot be subclassed, so they need no
entry here."""


def _value(x: object, /) -> object | None:
    """The value component of `cache_key` for `x`.

    Beartype matches `x` against `Literal[v]` exactly when `isinstance(x, type(v))`
    and `x == v`. The first half is settled by `type(x)`, which the key already
    carries; this slot settles the second half.

    An `x` that is not an instance of any legal `Literal` type can never match any
    `Literal`, so `type(x)` alone determines the answer and the slot is `None` — this
    is also what keeps unhashable arguments (a `list`, say) out of the key.

    Only an `x` of one of those types *exactly* is keyed on its value. Such an `x`
    has the built-in `__eq__` and `__hash__`, under which equal keys really do imply
    equal `x == literal` for every literal. A *subclass* instance can also match
    (`is_bearable(MyInt(1), Literal[1])` is `True`), but its `__eq__` and `__hash__`
    are user code and may be non-transitive, so two arguments could share a key while
    matching different literals. It is therefore keyed on its identity instead, which
    is strictly finer than its value and so never collides. This is the same
    precaution :class:`_Identity` already takes for classes.

    Args:
        x (object): Value.

    Returns:
        object or None: The value component of the cache key for `x`.
    """
    if type(x) in _LITERAL_TYPES:
        return x
    if isinstance(x, _LITERAL_BASES):
        # Note: this caches per object rather than per value. `Enum` members are
        # singletons, so for them the two coincide.
        return _Identity(x)
    return None


def cache_key(x: object, /, spec: CacheSpec = _ALL_PARTS) -> tuple[object, ...]:
    """Get a cache key for `x` with the parts in `spec`.

    If `is_cacheable(t)`, then whether `x` matches `t` depends only on `cache_key(x)`.
    The layout of the key is an implementation detail. The `IDENTITY` and `VALUE` parts
    can hold a reference to `x`.

    Args:
        x (object): Value.
        spec (CacheSpec, optional): Parts to include. Defaults to all parts.

    Returns:
        tuple: Cache key.
    """
    key: tuple[object, ...] = (type(x),)
    if KeyPart.IDENTITY in spec:
        key += (_identity(x),)
    if KeyPart.VALUE in spec:
        key += (_value(x),)
    return key


_ARG_KEYS: "dict[CacheSpec, Callable[[object], object]]" = {
    _NO_PARTS: type,
    _IDENTITY: lambda x: (type(x), _identity(x)),
    _VALUE: lambda x: (type(x), _value(x)),
    _IDENTITY | _VALUE: lambda x: (type(x), _identity(x), _value(x)),
}
"""`cache_key` specialised to each combination of spec, for :class:`.Resolver` to
bind on the hot path. Testing `KeyPart` membership per call costs ~80 ns per key part
(hashing an `Enum` member is not cheap), which is the bulk of a cached dispatch; these
do the same work with the spec already decided. One entry per subset of `KeyPart`;
`test_arg_keys_agree_with_cache_key` holds them to `cache_key`."""


def is_faithful(x: object, /) -> bool:
    """Check whether a type hint is faithful.

    A type or type hint `t` is _faithful_ if, for all `x`::

        isinstance(x, t) == issubclass(type(x), t)

    You can control whether types are faithful or not by setting the attribute
    `__faithful__`::

        class UnfaithfulType:
            __faithful__ = False

    See also :func:`is_cacheable`.

    Args:
        x (type or type hint): Type hint.

    Returns:
        bool: Whether `x` is faithful or not.
    """
    return _cache_spec(resolve_type_hint(x)) == _NO_PARTS


def is_cacheable(x: object, /) -> bool:
    """Check whether a type hint is cacheable.

    A type or type hint `t` is _cacheable_ if, for all `x`, whether `x` matches `t`
    depends only on `cache_key(x)`. Every faithful type is cacheable. `type[X]` and
    `Literal[...]` are cacheable, but not faithful.

    Args:
        x (type or type hint): Type hint.

    Returns:
        bool: Whether `x` is cacheable or not.
    """
    return _cache_spec(resolve_type_hint(x)) is not None


def _combine(items: Iterable[object], /) -> CacheSpec | None:
    """Union the specs of `items`, or `None` if any item is not cacheable."""
    acc = _NO_PARTS
    for item in items:
        sub = _cache_spec(resolve_type_hint(item))
        if sub is None:
            return None
        # `acc` is a shared instance, so a repeated spec skips the union.
        if sub is not acc:
            acc = _CANONICAL_SPECS[acc | sub]
    return acc


def _cache_spec(x: object, /) -> CacheSpec | None:
    """Determine the parts of the cache key that a type hint needs.

    Args:
        x (type or type hint): Resolved type hint.

    Returns:
        CacheSpec or None: Parts of the cache key, or `None` if `x` is not cacheable.
    """
    if _is_hint(x):
        origin = get_origin(x)
        args = get_args(x)
        if args == ():
            if origin is tuple and hasattr(x, "__args__"):
                # `tuple[()]` matches only the empty tuple, but from Python 3.11
                # `get_args` returns `()` for it. Unlike `typing.Tuple`, it has
                # `__args__`.
                return None
            # Unsubscripted hints tend to be faithful: `Any`, `List`, `Callable`, ...
            return _NO_PARTS
        if origin is type:
            # `issubclass(x, X)` depends only on `x` if `X` is faithful.
            return _IDENTITY if _combine(args) is _NO_PARTS else None
        if origin is Literal:
            return _VALUE
        if origin in UNION_TYPES:
            return _combine(args)
        return None

    elif x is None or x is Ellipsis:
        return _NO_PARTS

    elif isinstance(x, (tuple, list)):
        return _combine(x)

    elif isinstance(x, type):
        if _has_dunder_faithful(x):
            return _NO_PARTS if x.__faithful__ else None
        # This is the fallback method. Check whether `__instancecheck__` is default or
        # not. If it is, assume that it is faithful.
        faithful = type(x).__instancecheck__ in {
            type.__instancecheck__,
            abc.ABCMeta.__instancecheck__,
        }
        return _NO_PARTS if faithful else None

    else:
        warnings.warn(
            f"Could not determine whether `{x}` is faithful or cacheable. "
            f"I have concluded that it is neither, so your code might run "
            f"with subpar performance. "
            f"Please open an issue at https://github.com/beartype/plum.",
            stacklevel=2,
        )
    return None
