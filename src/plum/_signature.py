"""Signature and utilities for extracting signatures from callables."""

__all__ = ("Signature", "append_default_args", "inspect_signature")

import inspect
import operator
from collections.abc import Callable, Iterable
from copy import copy
from typing import Annotated, Any, ClassVar, get_args, get_origin, get_type_hints
from typing_extensions import Self

from rich.console import Console, ConsoleOptions
from rich.segment import Segment

from beartype.peps import resolve_pep563 as beartype_resolve_pep563

from ._bear import is_bearable, is_bearable_with_orig
from ._type import (
    UNION_TYPES,
    CacheSpec,
    _combine,
    _has_generic_hint,
    _type_hint_eq,
    _type_hint_le,
    is_faithful,
    resolve_type_hint,
)
from ._util import (
    Comparable,
    Missing,
    TypeHint,
    _MissingType,
    wrap_lambda,
)
from .repr import repr_short, rich_repr


def _class_is_honest(t: type, /) -> bool:
    """Whether instances of `t` report `type(self)` as their `__class__`.

    A class that overrides `__class__` -- with a property, say -- makes `isinstance`
    depend on the *value* rather than on its type. Anything keyed on `type(v)` has to
    treat such a type as unable to rule anything out. Only asked while a bucket is
    being built, once per distinct tuple of runtime types, so a short walk is fine.
    """
    return all("__class__" not in vars(c) for c in t.__mro__ if c is not object)


def _might_match_hint(v: object, t: TypeHint, /) -> bool:
    """Check whether *any* object with the runtime type of `v` could match hint `t`.

    Never `False` when `is_bearable(v, t)` is `True`, and never `False` for a `v` of
    this type when it is `True` for another. See :meth:`Signature.might_match`.

    Args:
        v (object): Value.
        t (:obj:`.TypeHint`): Type hint.

    Returns:
        bool: `False` only if no object with the runtime type of `v` matches `t`.
    """
    if is_faithful(t):
        # A faithful hint is *defined* by `isinstance(x, t) == issubclass(type(x), t)`,
        # so matching depends on nothing but `type(v)` and this is exact -- except for
        # the values that break that very equality. An object overriding `__class__`
        # is matched by `isinstance` while `issubclass(type(v), t)` says otherwise, so
        # for such a type the hint is not faithful about *this* value and nothing can
        # be ruled out. See `_class_is_honest`.
        return not _class_is_honest(type(v)) or bool(is_bearable(v, t))

    origin = get_origin(t)
    if origin in UNION_TYPES:
        # A union is matched precisely if one of its members is.
        return any(_might_match_hint(v, arg) for arg in get_args(t))
    if origin is Annotated:
        # The metadata of an `Annotated` can only reject further, so whether the
        # underlying hint could match decides.
        return _might_match_hint(v, get_args(t)[0])

    # Otherwise only the origin of the hint is settled by `type(v)`: whatever matches
    # `list[int]` is at any rate a `list`. That is a necessary condition when the
    # origin is a faithful class. Anything else (`Literal[...]`, an origin with a
    # custom `__instancecheck__`, a hint without an origin) cannot be ruled out.
    #
    # `issubclass(type(v), origin)`, not `isinstance(v, origin)`: the latter consults
    # `v.__class__`, so two values with the same runtime type can answer differently,
    # and a bucket keyed on `type(v)` would then be built from one of them and reused
    # for the other. Ruling a method out on that basis is a wrong dispatch, so a type
    # whose instances can lie about `__class__` rules nothing out at all.
    return (
        not isinstance(origin, type)
        or not is_faithful(origin)
        or not _class_is_honest(type(v))
        or issubclass(type(v), origin)
    )


@rich_repr
class Signature(Comparable):
    """Object representing a call signature that may be used to dispatch a function
    call.

    This object differs structurally from the return value of :func:`inspect.signature`
    as it only contains information necessary for performing dispatch.

    For example, for the current implementation of Plum, which does not dispatch on
    keyword arguments, those are left out of this signature object. Similarly, return
    type information and argument names are not present.

    Attributes:
        types (tuple[:obj:`.TypeHint`, ...]): Types of the call signature.
        varargs (type or :class:`.util.Missing`): Type of the variable number of
            arguments.
        has_varargs (bool): Whether `varargs` is not :class:`.util.Missing`.
        precedence (int): Precedence.
        cache_spec (frozenset | None): The cache spec this signature's types need, or
            `None` if any type is uncacheable. See :func:`plum.is_cacheable`.
    """

    _default_varargs: ClassVar = Missing
    _default_precedence: ClassVar[int] = 0

    __slots__: tuple[str, ...] = (
        "types",
        "varargs",
        "precedence",
        "cache_spec",
        "_check",
        "_matchers",
    )

    def __init__(
        self,
        *types: TypeHint,
        varargs: TypeHint | _MissingType = _default_varargs,
        precedence: int = _default_precedence,
    ) -> None:
        """Instantiate a signature, which contains exactly the information necessary for
        dispatch.

        Args:
            *types (:obj:`.TypeHint`): Types of the arguments.
            varargs (:obj:`.TypeHint`, optional): Type of the variable arguments.
            precedence (int, optional): Precedence. Defaults to `0`.
        """
        self.types = types
        self.varargs = varargs
        self.precedence = precedence

        all_types = types if self.varargs is Missing else (*types, self.varargs)
        self.cache_spec: CacheSpec | None = _combine(all_types)
        # Bind the matcher once, rather than testing a flag on every match: a
        # signature with no user generic anywhere gets plain `is_bearable`, exactly
        # the function it always used.
        check: Callable[[object, TypeHint], bool] = is_bearable
        for t in all_types:
            # A plain class can never be a *parametrised* generic, and is what almost
            # every annotation is, so it is ruled out inline: a generator expression
            # here costs more than the whole rest of the test.
            if not isinstance(t, type) and _has_generic_hint(t):
                check = is_bearable_with_orig
                break
        self._check = check
        # Bound matchers, by arity; see `_matcher`. `None` until one is asked for,
        # since only a signature reached through the tier-two path ever needs one.
        self._matchers: dict[int, Callable[[tuple[object, ...]], bool]] | None = None

    @staticmethod
    def from_callable(f: Callable[..., Any], precedence: int = 0) -> "Signature":
        """Construct a signature from a callable.

        Args:
            f (Callable): Callable.
            precedence (int, optional): Precedence. Defaults to 0.

        Returns:
            :class:`Signature`: Signature for `f`.
        """
        types, varargs = _extract_signature(f)
        return Signature(
            *types,
            varargs=varargs,
            precedence=precedence,
        )

    @property
    def has_varargs(self) -> bool:
        return self.varargs is not Missing

    @property
    def is_faithful(self) -> bool:
        """Whether every type is faithful (the cache can key on `type(x)` alone)."""
        return self.cache_spec == frozenset()

    def __copy__(self) -> Self:
        cls = type(self)
        copy = cls.__new__(cls)
        for attr in self.__slots__:
            setattr(copy, attr, getattr(self, attr))

        # `append_default_args` copies a signature and then rewrites `types` and
        # `varargs` on the copy. A matcher is bound to the arity and types it was
        # built from, so carrying one across that would answer for the original.
        copy._matchers = None
        return copy

    def __rich_console__(
        self, console: Console, options: ConsoleOptions, /
    ) -> Iterable[Segment]:
        yield Segment("Signature(")
        show_comma = True
        if self.types:
            yield Segment(", ".join(map(repr_short, self.types)))
        if self.varargs != Signature._default_varargs:
            if show_comma:
                yield Segment(", ")
            yield Segment("varargs=" + repr_short(self.varargs))
        if self.precedence != Signature._default_precedence:
            if show_comma:
                yield Segment(", ")
            yield Segment("precedence=" + repr(self.precedence))
        yield Segment(")")

    def __eq__(self, other: Any, /) -> bool:
        if not isinstance(other, Signature):
            return False

        # Settle the scalar properties first: any of them differing rules equality
        # out, and wrapping the types is the expensive part.
        if (
            len(self.types) != len(other.types)
            or (self.varargs is Missing) != (other.varargs is Missing)
            or self.precedence != other.precedence
        ):
            return False

        # We don't need to check faithfulness, because that is automatically
        # derived from the arguments.
        #
        # Use `_type_hint_eq` rather than comparing `TypeHintWrapper`s directly
        # so that `Any` only equals `Any` itself; see its docstring.
        types_equal = all(
            _type_hint_eq(x, y) for x, y in zip(self.types, other.types, strict=True)
        )
        # The guard above settled precedence, and that the two agree on *whether* they
        # have varargs; all that is left is comparing them when both do.
        varargs_equal = self.varargs is Missing or _type_hint_eq(
            self.varargs, other.varargs
        )
        return types_equal and varargs_equal

    def __hash__(self) -> int:
        return hash((Signature, *self.types, self.varargs))

    def expand_varargs(self, n: int) -> tuple[TypeHint, ...]:
        """Expand variable arguments.

        Args:
            n (int): Desired number of types.

        Returns:
            tuple[type, ...]: Expanded types.
        """
        if self.has_varargs:
            expansion_size = max(n - len(self.types), 0)
            return self.types + (self.varargs,) * expansion_size
        else:
            return self.types

    def __le__(self, other: object, /) -> bool:
        if not isinstance(other, Signature):
            return NotImplemented
        # If the number of types of the signatures are unequal, then the signature
        # with the fewer number of types must be expanded using variable arguments.
        if not (
            len(self.types) == len(other.types)
            or (len(self.types) > len(other.types) and other.has_varargs)
            or (len(self.types) < len(other.types) and self.has_varargs)
        ):
            return False

        # Expand the types and compare. We implement the subset relationship,
        # but, very importantly, deviate from the subset relationship in exactly
        # one place.
        self_types = self.expand_varargs(len(other.types))
        other_types = other.expand_varargs(len(self.types))
        # As in `__eq__`, use `_type_hint_eq` so that `Any` only equals `Any`
        # itself; see its docstring.
        if all(
            _type_hint_eq(x, y) for x, y in zip(self_types, other_types, strict=True)
        ):
            if self.has_varargs and other.has_varargs:
                return _type_hint_le(self.varargs, other.varargs)

            # Having variable arguments makes you slightly larger.
            elif self.has_varargs:
                return False
            elif other.has_varargs:
                return True

            else:
                return True

        # As above, use `_type_hint_le` so that `Any` is only a subhint of `Any`
        # itself; see its docstring.
        elif all(
            _type_hint_le(x, y) for x, y in zip(self_types, other_types, strict=True)
        ):
            # In this case, we have that `other >= self` is `False`, so returning `True`
            # gives that `other < self` and returning `False` gives that `other` cannot
            # be compared to `self`. Regardless of the return value, `other != self`.

            if self.has_varargs and other.has_varargs:
                # TODO: This implements the subset relationship. However, if the
                #       variable arguments are not used, then this may unnecessarily
                #       return `False`. For example, `(int, *A)` would not be
                #       comparable to `(Number, *B)`. However, if the argument given
                #       is `1.0`, then reasonably the variable arguments should be
                #       ignored and `(int, *A)` should be considered more specific
                #       than `(Number, *B)`.
                return _type_hint_le(self.varargs, other.varargs)

            elif self.has_varargs:
                # Previously, this returned `False`, which would implement the subset
                # relationship. We now deviate from the subset relationship! The
                # rationale for this is as follows.
                #
                # A non-variable-arguments signature is compared to a variable-arguments
                # signature only to determine which is more specific. At this point, the
                # non-variable-arguments signature has number of types equal to the
                # number of arguments given to the function, so any additional variable
                # arguments are not necessary. Hence, we ignore the additional
                # variable arguments in the comparison and return correctly `True`. For
                # example, `(int, *int)` would be more specific than `(Number)`.
                return True
            elif other.has_varargs:
                return True

            else:
                return True

        else:
            return False

    def is_comparable(self, other: object, /) -> bool:
        """Check whether this signature is comparable with another one.

        Two signatures are comparable exactly when one is below the other, so one
        `__le__` per direction settles it, and the first direction short-circuits.
        The inherited implementation spells the same question as `self < other or
        self == other or self > other`, which additionally runs :meth:`__eq__` twice.

        Args:
            other (object): Object to check comparability with.

        Returns:
            bool: Whether this signature is comparable with `other`.
        """
        return isinstance(other, Signature) and (self <= other or other <= self)

    def match(self, values: tuple[object, ...], /) -> bool:
        """Check whether values match the signature.

        Args:
            values (tuple): Values.

        Returns:
            bool: `True` if `values` match this signature and `False` otherwise.
        """
        # `values` must either be exactly many as `self.types`. If there are more
        # `values`, then there must be variable arguments to cover the arguments.
        if not (
            len(self.types) == len(values)
            or (len(self.types) < len(values) and self.has_varargs)
        ):
            return False
        else:
            types = self.expand_varargs(len(values))
            check = self._check
            return all(check(v, t) for v, t in zip(values, types, strict=True))

    def might_match(self, values: tuple[object, ...], /) -> bool:
        """Check whether *any* values with the runtime types of `values` could match.

        This is :meth:`match` weakened to depend only on `tuple(map(type, values))`.
        It may be `True` where :meth:`match` is `False`, but it is never `False`
        where :meth:`match` is `True`. That is what makes it sound to bucket methods
        by the bare runtime types of the arguments: a method left out of a bucket
        cannot match any arguments with those types.

        Args:
            values (tuple): Values.

        Returns:
            bool: `False` only if no values with these runtime types can match this
                signature.
        """
        # Arity is settled by the number of values alone, so this is exact.
        if not (
            len(self.types) == len(values)
            or (len(self.types) < len(values) and self.has_varargs)
        ):
            return False

        return all(
            _might_match_hint(v, t)
            for v, t in zip(values, self.expand_varargs(len(values)), strict=True)
        )

    def compute_distance(self, values: tuple[object, ...], /) -> int:
        """For given values, computes the edit distance between these vales and this
        signature.

        Args:
            values (tuple[object, ...]): Values.

        Returns:
            int: Edit distance.
        """
        n = len(values)
        types = self.expand_varargs(n)

        # Count one for every extra or missing argument.
        distance: int = abs(len(types) - n)

        # Additionally count one for every mismatching value above the
        # extra/missing arguments. There can be fewer types than values.
        check = self._check
        for v, t in zip(values, types, strict=False):
            if not check(v, t):
                distance += 1

        return distance

    def compute_mismatches(
        self, values: tuple[object, ...], /
    ) -> tuple[frozenset[int], bool]:
        """For given `values`, find the indices of the arguments that are mismatched.
        Also return whether the varargs is matched.

        Args:
            values (tuple[object, ...]): Values.

        Returns:
            frozenset[int]: Indices of invalid values.
            bool: Whether the varargs was matched or not.
        """
        types = self.expand_varargs(len(values))

        n_types = len(self.types)
        mismatches = set()
        # By default, the varargs are matched. Only return that it is mismatched if
        # there is an explicit mismatch.
        varargs_matched = True

        check = self._check
        for i, (v, t) in enumerate(zip(values, types, strict=False)):
            if not check(v, t):
                if i < n_types:
                    mismatches.add(i)
                else:
                    varargs_matched = False

        return frozenset(mismatches), varargs_matched


def _matcher(signature: Signature, n: int, /) -> Callable[[tuple[object, ...]], bool]:
    """:func:`_bind_matcher`, memoised on the signature and the arity.

    A matcher is fixed by the signature and the arity and by nothing else, but a
    verify-cache bucket is keyed on the runtime *types* of the arguments, so without
    this every bucket would bind its own copy of the same matcher for every method it
    holds -- a 248-byte closure per method per bucket, against at most one per method
    per arity. See :meth:`.function.Function._build_verify_bucket`.

    Args:
        signature (:class:`Signature`): Signature to bind a matcher for.
        n (int): Number of values the matcher will be given.

    Returns:
        function: Callable that takes a tuple of `n` values and returns whether they
            match `signature`.
    """
    cache = signature._matchers
    if cache is None:
        cache = signature._matchers = {}
    bound = cache.get(n)
    if bound is None:
        bound = cache[n] = _bind_matcher(signature, n)
    return bound


def _bind_matcher(
    signature: Signature, n: int, /
) -> Callable[[tuple[object, ...]], bool]:
    """Bind a matcher for tuples of exactly `n` values.

    This is :meth:`Signature.match` with the arity check and the expansion of the
    variable arguments done once, here, instead of on every call. It is only correct
    for tuples of `n` values, so the caller must know the arity up front -- which a
    cache keyed on the types of the arguments does.

    A module-level function rather than a method, because `mypyc` crashes with an
    internal `AssertionError` on a closure inside a method of a class carrying a
    decorator it does not recognise, which :class:`Signature` does
    (:func:`.repr.rich_repr`). Keeping the closures means the bound matcher stays
    exactly the plain function call it was on the hot path.

    Args:
        signature (:class:`Signature`): Signature to bind a matcher for.
        n (int): Number of values the matcher will be given.

    Returns:
        function: Callable that takes a tuple of `n` values and returns whether they
            match `signature`.
    """
    types_ = signature.types
    if not (len(types_) == n or (len(types_) < n and signature.has_varargs)):
        return lambda values: False
    types = signature.expand_varargs(n)
    check = signature._check
    if n == 1:
        # By far the most common arity, and worth not paying a `zip` for.
        (t,) = types
        return lambda values: check(values[0], t)
    return lambda values: all(check(v, t) for v, t in zip(values, types, strict=True))


def inspect_signature(f: Callable[..., Any], /) -> inspect.Signature:
    """Wrapper of :func:`inspect.signature` which adds support for certain non-function
    objects.

    Args:
        f (object): Function-like object.

    Returns:
        object: Signature.
    """
    if isinstance(f, (operator.itemgetter, operator.attrgetter)):
        f = wrap_lambda(f)
    return inspect.signature(f)


def resolve_pep563(f: Callable[..., Any], /) -> None:
    """Utility function to resolve PEP563-style annotations and make editable.

    This function mutates `f`.

    Args:
        f (Callable): Function whose annotations should be resolved.
    """
    if hasattr(f, "__annotations__"):
        beartype_resolve_pep563(f)  # This mutates `f`.
        # Override the `__annotations__` attribute, since `resolve_pep563` modifies
        # `f` too.
        for k, v in get_type_hints(f, include_extras=True).items():
            f.__annotations__[k] = v


def _extract_signature(
    f: Callable[..., Any], /, precedence: int = 0
) -> tuple[list[TypeHint], TypeHint | _MissingType]:
    """Extract the signature from a function.

    Args:
        f (function): Function to extract signature from.
        precedence (int, optional): Precedence of the method.

    Returns:
        tuple: A tuple of (types_list, varargs).
    """
    resolve_pep563(f)

    # Extract specification.
    sig = inspect_signature(f)

    # Get types of arguments.
    types: list[TypeHint] = []
    varargs: TypeHint | _MissingType = Missing
    for arg in sig.parameters:
        p = sig.parameters[arg]

        # Parse and resolve annotation.
        if p.annotation is inspect.Parameter.empty:
            annotation: TypeHint = Any
        else:
            annotation = resolve_type_hint(p.annotation)

        # Stop once we have seen all positional parameter without a default value.
        if p.kind in {p.KEYWORD_ONLY, p.VAR_KEYWORD}:
            break

        if p.kind == p.VAR_POSITIONAL:
            # Parameter indicates variable arguments.
            varargs = annotation
        else:
            # Parameter is a regular positional parameter.
            types.append(annotation)

        # If there is a default parameter, make sure that it is of the annotated type.
        default_is_empty = p.default is inspect.Parameter.empty
        if not default_is_empty and not is_bearable(p.default, annotation):
            raise TypeError(
                f"Default value `{p.default}` is not an instance "
                f"of the annotated type `{repr_short(annotation)}`."
            )

    return types, varargs


def append_default_args(signature: Signature, f: Callable[..., Any]) -> list[Signature]:
    """Returns a list of signatures of function `f`, where those signatures are derived
    from the input arguments of `f` by treating every non-keyword-only argument with a
    default value as a keyword-only argument turn by turn.

    Args:
        f (function): Function to extract default arguments from.
        signature (:class:`.signature.Signature`): Signature of `f` from which to
            remove default arguments.

    Returns:
        list[:class:`.signature.Signature`]: List of signatures excluding from no to all
            default arguments.
    """
    # Extract specification.
    f_signature = inspect_signature(f)

    signatures = [signature]

    arg_names = list(f_signature.parameters.keys())[: len(signature.types)]
    # We start at the end and, once we reach non-keyword-only arguments, delete the
    # argument with defaults values one by one. This generates a sequence of signatures,
    # which we return.
    arg_names.reverse()

    for arg in arg_names:
        p = f_signature.parameters[arg]

        # Ignore variable arguments and keyword arguments.
        if p.kind in {p.VAR_KEYWORD, p.KEYWORD_ONLY}:
            continue

        # Stop when non-variable arguments without a default are reached.
        if p.kind != p.VAR_POSITIONAL and p.default is inspect.Parameter.empty:
            break

        # Skip variable arguments. These will always be removed.
        if p.kind == p.VAR_POSITIONAL:
            continue

        signature_copy = copy(signatures[-1])

        # As specified over, these additional signatures should never have variable
        # arguments.
        signature_copy.varargs = Missing

        # Remove the last positional argument.
        signature_copy.types = signature_copy.types[:-1]

        signatures.append(signature_copy)

    return signatures
