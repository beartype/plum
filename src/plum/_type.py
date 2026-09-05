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
import sys
import typing
import warnings
from collections.abc import Callable, Hashable, Iterable
from functools import lru_cache, reduce
from operator import or_
from types import UnionType
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
        if x.__module__ == "builtins":
            # Check if `x` is a subscripted built-in. We do this by checking the module
            # of the type of `x`.
            x = type(x)
        return x.__module__ in {
            "types",  # E.g., `tuple[int]`
            "typing",
            "collections.abc",  # E.g., `Callable`
            "typing_extensions",
        }
    except AttributeError:
        return False


def _is_generic_hint(x: object, /) -> bool:
    """Check if an object is a parametrised :class:`typing.Generic` subclass.

    The test is that the origin is a class inheriting :class:`typing.Generic`, which
    is exactly the population whose parameter cannot be recovered from the value: such
    an instance records it in `__orig_class__` instead. Everything else is excluded by
    that same test rather than by name — the parametrised builtins (`list[int]`), the
    abstract base classes (`Sequence[int]`), `re.Pattern[str]` and
    `AbstractContextManager[int]` are not `Generic` subclasses and beartype checks
    them structurally, while `Annotated`, `Union`, `Optional`, `Literal` and
    `type[X]` have origins that are not classes at all. Plum's own parametric types
    have no origin.

    Deliberately *not* keyed on `__module__` (as :func:`_is_hint` is): a generic
    declared in an `exec`'d namespace, a doctest among them, reports its module as
    `builtins`, and its subscript is a `typing._GenericAlias`, so a module test
    mistakes it for a `typing` special form.

    Args:
        x (object): Object.

    Returns:
        bool: `True` if `x` is a parametrised user generic and `False` otherwise.
    """
    origin = get_origin(x)
    return (
        isinstance(origin, type)
        and issubclass(origin, typing.Generic)
        and get_args(x) != ()
    )


def _has_generic_hint(x: object, /) -> bool:
    """Check whether a parametrised user generic occurs anywhere in the hint `x`.

    This walks the arguments, so it also finds generics nested inside a union, an
    `Annotated`, or a parametrised builtin. It is computed once per signature, at
    registration, to keep the check off the matching path.

    Args:
        x (object): Type hint.

    Returns:
        bool: `True` if `x` contains a parametrised user generic.
    """
    if isinstance(x, type):
        # A parametrised generic is a `_GenericAlias`, never a class, and a class has
        # no arguments to recurse into. This is the common case at registration --
        # every plain annotation lands here -- and it skips two `typing` lookups.
        return False
    return _is_generic_hint(x) or any(_has_generic_hint(a) for a in get_args(x))


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

    # This sits below the plain-`type` case on purpose. `resolve_type_hint` runs twice
    # per call for any method with a return annotation (via `convert`), and a plain
    # type such as `int` is by far the commonest argument. Testing it here means such
    # a type returns above without ever paying for the origin lookup; a parametrised
    # user generic is not a `type`, so it still reaches this branch.
    elif _is_generic_hint(x):
        # A parametrised user generic, e.g. `Box[int]`. Rebuild it from its origin so
        # that a `ResolvableType` nested in its arguments is resolved too.
        origin = get_origin(x)
        assert origin is not None
        resolved_args = tuple(resolve_type_hint(arg) for arg in get_args(x))
        return origin[resolved_args]

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


def _wrap_type_hint_uncached(hint: object, /) -> TypeHintWrapper:
    return TypeHintWrapper(_substitute_any(hint))


_wrap_type_hint_cached = lru_cache(maxsize=4096)(_wrap_type_hint_uncached)


def _wrap_type_hint(hint: object, /) -> TypeHintWrapper:
    """Wrap `hint` for comparison, replacing every `Any` by `object`.

    `Signature` comparison wraps the same fixed hints on every uncached dispatch, so
    the rewrite and `beartype`'s own wrapper lookup would otherwise repeat per call.

    Args:
        hint (object): Already-resolved type hint.

    Returns:
        TypeHintWrapper: Wrapped hint.
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
    make an unannotated (`Any`-typed) parameter compare equal to, and as specific as,
    any concrete type. See https://github.com/beartype/plum/issues/295. For Plum's
    signature bookkeeping, `Any` must instead be the unique least specific type. This
    check therefore differs from `beartype.door.TypeHint(x) <= TypeHint(y)` in exactly
    one respect: a root `Any` is only a subhint of `Any`, and a nested `Any` is
    rewritten to `object` by `_substitute_any`, which reproduces `beartype<0.23`.

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
    if x is Any or y is Any:
        return x is y
    # Do not derive this from `_type_hint_le`: `TypeHintWrapper.__eq__` already checks
    # both directions in one pass.
    return bool(_wrap_type_hint(x) == _wrap_type_hint(y))


UNION_TYPES = (typing.Union, UnionType, typing.Optional)


class KeyPart(enum.Enum):
    """One component a dispatch cache key may have to carry, beyond `type(x)`.

    A faithful type needs none of these: `type(x)` settles its match on its own.
    Each member names a further property of the argument that `cache_key` must
    encode for a category of non-faithful types to become cacheable at all.
    `IDENTITY` is what makes `type[X]` cacheable, `VALUE` `Literal[...]`, and
    `GENERIC` a parametrised user generic such as `Box[int]`. Members are
    append-only, so a new category is an addition rather than a redesign.
    """

    IDENTITY = "identity"
    VALUE = "value"
    GENERIC = "generic"


CacheSpec = frozenset[KeyPart]
r"""What a type needs its cache key to carry: the set of :class:`KeyPart`\ s.

`frozenset()` is the faithful case -- `type(x)` alone suffices. `None`, wherever a
`CacheSpec` is optional, means *uncacheable*: no key can determine the match.
"""

_NO_PARTS: CacheSpec = frozenset()
_IDENTITY: CacheSpec = frozenset({KeyPart.IDENTITY})
_VALUE: CacheSpec = frozenset({KeyPart.VALUE})
_GENERIC: CacheSpec = frozenset({KeyPart.GENERIC})
_ALL_PARTS: CacheSpec = frozenset(KeyPart)


class _SupportsDunderFaithful(typing.Protocol):
    __faithful__: bool


def _has_dunder_faithful(x: type, /) -> TypeGuard[_SupportsDunderFaithful]:
    """Check whether `x` has the `__faithful__` attribute."""
    return hasattr(x, "__faithful__")


class _Identity:
    """Identity cache-key wrapper for an object whose hash or equality cannot be
    trusted.

    A class cannot be used as a cache key directly: its hash and equality come from
    its metaclass, so a metaclass with a custom `__eq__` would make distinct classes
    collide (silent wrong hit) and one whose classes are unhashable would make the
    key raise `TypeError`. The same applies to an unhashable value. This wrapper keys
    on `id`, sidestepping both, and holds a reference to `obj` so its `id` is not
    reused while the entry lives.
    """

    __slots__ = ("obj",)

    def __init__(self, obj: object, /) -> None:
        self.obj = obj

    def __hash__(self) -> int:
        return id(self.obj)

    def __eq__(self, other: object, /) -> bool:
        return type(other) is _Identity and self.obj is other.obj


def _identity(x: object, /) -> object | None:
    """The identity component of `cache_key` for `x`.

    `None` for non-classes. For a class, the class itself when its metaclass is plain
    `type` (whose hash is id-based and equality is identity — already safe and fast),
    otherwise the metaclass-safe `_Identity` wrapper.
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


def _generic(x: object, /) -> object | None:
    """The generic component of `cache_key` for `x`.

    A parametrised user generic is matched by :func:`._bear.is_bearable_with_orig`,
    which decides on `__orig_class__` — the parametrisation Python records on the
    instance — and falls back to `type(x)` when there is none. This slot is exactly
    that record, so the pair `(type(x), __orig_class__)` settles the match: two
    values sharing it are decided identically.

    `None` for a value that records no parametrisation, which is also the fallback
    the matcher itself uses. As elsewhere in plum, `__orig_class__` is trusted to be
    the type it claims: Python sets it, and so do :func:`plum.parametric` and
    :func:`plum.generic`.

    A parametrisation can itself be unhashable -- `Box[Annotated[int, {"a": 1}]]` is
    a legal thing to write -- and putting it in the key verbatim would make the key
    unhashable, so the dict lookup in `Function.__call__` would raise rather than
    dispatch. Fall back to keying on its identity, which is finer than the value and
    so never collides; the same precaution :func:`_value` takes.

    Args:
        x (object): Value.

    Returns:
        object or None: The generic component of the cache key for `x`.
    """
    orig = getattr(x, "__orig_class__", None)
    if orig is None or _hashable(orig):
        return orig
    return _Identity(orig)


def cache_key(x: object, /, spec: CacheSpec = _ALL_PARTS) -> tuple[object, ...]:
    """Cache key for a value `x`, carrying the key parts named by `spec`.

    For any hint `t` with `is_cacheable(t)`, whether `x` matches `t` depends only on
    `cache_key(x)`, so a dispatch result for `x` can be memoised under this key. A
    resolver passes only the key parts its own types need, so it never captures
    more than necessary.

    The exact width of the returned tuple and the order of its slots are an
    implementation detail: every member added to :class:`KeyPart` adds a slot to
    the default key. Only the contract is stable: equal keys imply the same match
    result.

    Note that the identity, value and generic slots keep a strong reference to `x`
    or to a type derived from it — necessarily,
    since that is what makes `id`-based hashing safe. A function dispatching on
    `type[X]` or `Literal` therefore accumulates one cache entry per distinct argument
    class or value, and pins that class or value, for the function's lifetime;
    dynamically created classes are not collected. Call `f.clear_cache()` (or
    :func:`plum.clear_all_cache`) to release them. Because a `Literal` argument's value
    is typically caller-supplied, a function dispatching on one stops caching once it
    holds `plum._function._VALUE_CACHE_LIMIT` entries; further arguments resolve
    normally.

    Args:
        x (object): Value to compute a cache key for.
        spec (:obj:`CacheSpec`, optional): Key parts to capture. Defaults to all
            of them.

    Returns:
        tuple: Cache key for `x`.
    """
    key: tuple[object, ...] = (type(x),)
    if KeyPart.IDENTITY in spec:
        key += (_identity(x),)
    if KeyPart.VALUE in spec:
        key += (_value(x),)
    if KeyPart.GENERIC in spec:
        key += (_generic(x),)
    return key


_ARG_KEYS: "dict[CacheSpec, Callable[[object], object]]" = {
    _NO_PARTS: type,
    _IDENTITY: lambda x: (type(x), _identity(x)),
    _VALUE: lambda x: (type(x), _value(x)),
    _GENERIC: lambda x: (type(x), _generic(x)),
    _IDENTITY | _VALUE: lambda x: (type(x), _identity(x), _value(x)),
    _IDENTITY | _GENERIC: lambda x: (type(x), _identity(x), _generic(x)),
    _VALUE | _GENERIC: lambda x: (type(x), _value(x), _generic(x)),
    _IDENTITY | _VALUE | _GENERIC: lambda x: (
        type(x),
        _identity(x),
        _value(x),
        _generic(x),
    ),
}
"""`cache_key` specialised to each combination of spec, for :class:`.Resolver` to
bind on the hot path. Testing `KeyPart` membership per call costs ~95 ns per key part
(hashing an `Enum` member is not cheap), and building the key by concatenation rather
than as one tuple costs a further ~45 ns per part; together that is most of the cost of
a cached dispatch. These do the same work with the spec already decided.

One entry per subset of `KeyPart`, so a fourth member would double this to sixteen. At
that point stop writing them out: keep a per-part table of `(KeyPart, getter)` and
generate the callable from the getters a spec selects, with one branch per arity so
that each stays a fixed-width tuple literal. That was measured at within ~10 ns of
these, but it is longer than the table at three members, which is why the table is
still here. `test_arg_keys_agree_with_cache_key` holds them to `cache_key`."""


def is_faithful(x: object, /) -> bool:
    """Check whether a type hint is faithful.

    A type or type hint `t` is _faithful_ if, for all `x`::

        isinstance(x, t) == issubclass(type(x), t)

    i.e. matching depends only on `type(x)`. Faithful types are cacheable with a plain
    `type(x)` key. You can control faithfulness by setting `__faithful__`::

        class UnfaithfulType:
            __faithful__ = False

    `type[X]` is *not* faithful (its match depends on class identity); see
    :func:`is_cacheable`.

    Args:
        x (type or type hint): Type hint.

    Returns:
        bool: Whether `x` is faithful or not.
    """
    return _cache_spec(resolve_type_hint(x)) == _NO_PARTS


def is_cacheable(x: object, /) -> bool:
    """Check whether a type hint is cacheable.

    `t` is _cacheable_ if, for all `x`, whether `x` matches `t` is a function of
    :func:`cache_key(x) <cache_key>` alone. Every faithful type is cacheable; in
    addition `type[X]` is cacheable but not faithful (its match `issubclass(x, X)`
    depends on the class identity of `x`, which `cache_key` captures), and so are
    `Literal[...]` (its match depends on the value of `x`, likewise captured) and a
    parametrised user generic such as `Box[int]` (its match depends on the `x`'s
    `__orig_class__`, likewise captured).

    A parametrised *builtin* such as `list[int]` is not cacheable: matching it
    inspects the elements, so two values of the same type can match differently.

    Args:
        x (type or type hint): Type hint.

    Returns:
        bool: Whether `x` is cacheable or not.
    """
    return _cache_spec(resolve_type_hint(x)) is not None


_CANONICAL_SPECS: "dict[CacheSpec, CacheSpec]" = {}
"""One shared instance per distinct :obj:`CacheSpec`, populated on demand.

A `frozenset` union always allocates, and `frozenset() | frozenset()` is not the
empty singleton, so without this every signature and every resolver would hold a
private 216-byte copy of one of only `2 ** len(KeyPart)` possible values. Interning
them costs one dict lookup at registration, which is cold, and the table cannot grow
past that many entries."""


def _canonical(spec: CacheSpec, /) -> CacheSpec:
    """The shared instance equal to `spec`, interning it if it is the first."""
    return _CANONICAL_SPECS.setdefault(spec, spec)


def _combine(items: "Iterable[object]", /) -> CacheSpec | None:
    """Union the specs of `items` (each resolved); `None` if any is uncacheable."""
    acc = _NO_PARTS
    for item in items:
        sub = _cache_spec(resolve_type_hint(item))
        if sub is None:
            return None
        if sub is not acc:
            # Almost every signature is uniform, so this skips the allocation that
            # `|=` would make on every argument.
            acc |= sub
    return _canonical(acc)


def _cache_spec(x: object, /) -> CacheSpec | None:
    """Classify a **resolved** hint into the :obj:`CacheSpec` it needs, or `None`.

    `frozenset()` = faithful (type-key suffices); `{IDENTITY}` = `type[X]`;
    `{VALUE}` = `Literal[...]`; `{GENERIC}` = a parametrised user generic; a union is
    the union of its members (`None` if any member is uncacheable); everything else
    that is not a plainly faithful type is `None` (uncacheable). This is the single
    classifier `is_faithful` and `is_cacheable` derive from.
    """
    if _is_hint(x):
        origin = get_origin(x)
        args = get_args(x)
        if args == ():
            if origin is tuple and hasattr(x, "__args__"):
                # `tuple[()]` is the one hint that is subscripted yet reports no
                # arguments: `get_args(tuple[()])` is `()` on Python >= 3.11. It
                # matches on the *length* of the value, not its type, so it is
                # neither faithful nor cacheable. Bare `typing.Tuple` shares the
                # `tuple` origin but matches on type alone, and is told apart by
                # having no `__args__` at all.
                return None
            # Unsubscripted hints tend to be faithful: `Any`, `List`, `Callable`, ...
            return _NO_PARTS
        if origin is type:
            # `type[X]`: cacheable via the identity component of the cache key.
            return _IDENTITY
        if origin is Literal:
            # `Literal[...]`: cacheable via the value component of the cache key.
            return _VALUE
        if origin in UNION_TYPES:
            return _combine(args)
        if _is_generic_hint(x):
            # A parametrised user generic can land here rather than in the branch
            # below: `_is_hint` decides on `__module__`, and a generic declared in an
            # `exec`'d namespace -- a doctest among them -- reports `builtins`, the
            # same module as `list[int]`. Classify it on what it is, not where it was
            # written; `_is_generic_hint` tests for inheritance from `typing.Generic`,
            # which no parametrised builtin and no `typing` special form satisfies.
            return _GENERIC
        return None

    elif x is None or x is Ellipsis:
        return _NO_PARTS

    elif isinstance(x, (tuple, list)):
        return _combine(x)

    elif isinstance(x, type):
        if _has_dunder_faithful(x):
            return _NO_PARTS if x.__faithful__ else None
        # Fallback: default `__instancecheck__` ⇒ faithful.
        faithful = type(x).__instancecheck__ in {
            type.__instancecheck__,
            abc.ABCMeta.__instancecheck__,
        }
        return _NO_PARTS if faithful else None

    elif _is_generic_hint(x):
        # A parametrised user generic, e.g. `Box[int]`. Whether a value matches
        # depends on its `__orig_class__` and on nothing else — see
        # `is_bearable_with_orig`, which falls back to `type(x)` when there is no
        # such record — and the generic component of the cache key is precisely
        # that. Ordered below the plain-`type` case for the same reason as in
        # `resolve_type_hint`.
        #
        # Note how narrow this is: it holds only for hints that go through
        # `__orig_class__`. A parametrised builtin such as `list[int]` is matched by
        # inspecting the elements, which no key derived from the value's type can
        # predict, and `_is_generic_hint` excludes it. That exclusion is what keeps
        # this sound, so do not widen it.
        return _GENERIC

    else:
        warnings.warn(
            f"Could not determine whether `{x}` is faithful or cacheable. "
            f"I have concluded that it is neither, so your code might run "
            f"with subpar performance. "
            f"Please open an issue at https://github.com/beartype/plum.",
            stacklevel=2,
        )
    return None
