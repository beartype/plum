import inspect
import operator
import typing
from copy import copy
from typing import Callable, List, Set, Tuple, Union

import beartype.door
from beartype.peps import resolve_pep563 as beartype_resolve_pep563
from rich.segment import Segment

from . import _is_bearable
from .repr import repr_short, rich_repr
from .type import is_faithful, resolve_type_hint
from .typing import get_type_hints
from .util import Comparable, Missing, TypeHint, multihash, wrap_lambda

__all__ = ["Signature", "append_default_args"]

OptionalType = Union[TypeHint, type(Missing)]


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
        is_faithful (bool): Whether this signature only uses faithful types.
    """

    _default_varargs = Missing
    _default_precedence = 0

    __slots__ = ("types", "varargs", "precedence", "is_faithful")

    def __init__(
        self,
        *types: Tuple[TypeHint, ...],
        varargs: OptionalType = _default_varargs,
        precedence: int = _default_precedence,
    ):
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

        types_are_faithful = all(is_faithful(t) for t in types)
        varargs_are_faithful = self.varargs is Missing or is_faithful(self.varargs)
        self.is_faithful = types_are_faithful and varargs_are_faithful

    @staticmethod
    def from_callable(f: Callable, precedence: int = 0) -> "Signature":
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

    def __copy__(self):
        cls = type(self)
        copy = cls.__new__(cls)

        copy.types = self.types
        copy.varargs = self.varargs
        copy.precedence = self.precedence
        copy.is_faithful = self.is_faithful
        return copy

    def __rich_console__(self, console, options):
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

    def __eq__(self, other):
        if isinstance(other, Signature):
            return (
                self.types,
                self.varargs,
                self.precedence,
                self.is_faithful,
            ) == (
                other.types,
                other.varargs,
                other.precedence,
                other.is_faithful,
            )
        return False

    def __hash__(self):
        return multihash(Signature, *self.types, self.varargs)

    def expand_varargs(self, n: int) -> Tuple[TypeHint, ...]:
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

    def __le__(self, other) -> bool:
        # If this signature has variable arguments, but the other does not, then this
        # signature cannot be possibly smaller.
        if self.has_varargs and not other.has_varargs:
            return False

        # If this signature and the other signature both have variable arguments, then
        # the variable type of this signature must be less than the variable type of the
        # other signature.
        if (
            self.has_varargs
            and other.has_varargs
            and not (
                beartype.door.TypeHint(self.varargs)
                <= beartype.door.TypeHint(other.varargs)
            )
        ):
            return False

        # If the number of types of the signatures are unequal, then the signature
        # with the fewer number of types must be expanded using variable arguments.
        if not (
            len(self.types) == len(other.types)
            or (len(self.types) > len(other.types) and other.has_varargs)
            or (len(self.types) < len(other.types) and self.has_varargs)
        ):
            return False

        # Finally, expand the types and compare.
        self_types = self.expand_varargs(len(other.types))
        other_types = other.expand_varargs(len(self.types))
        return all(
            [
                beartype.door.TypeHint(x) <= beartype.door.TypeHint(y)
                for x, y in zip(self_types, other_types)
            ]
        )

    def match(self, values) -> bool:
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
            return all(_is_bearable(v, t) for v, t in zip(values, types))

    def compute_distance(self, values: Tuple[object, ...]) -> int:
        """For given values, computes the edit distance between these vales and this
        signature.

        Args:
            values (tuple[object, ...]): Values.

        Returns:
            int: Edit distance.
        """
        types = self.expand_varargs(len(values))

        distance = 0

        # Count one for every extra or missing argument.
        distance += abs(len(types) - len(values))

        # Additionally count one for every mismatching value.
        for v, t in zip(values, types):
            if not _is_bearable(v, t):
                distance += 1

        return distance

    def compute_mismatches(self, values: Tuple) -> Tuple[Set[int], bool]:
        """For given `values`, find the indices of the arguments that are mismatched.
        Also return whether the varargs is matched.

        Args:
            values (tuple[object, ...]): Values.

        Returns:
            set[int]: Indices of invalid values.
            bool: Whether the varargs was matched or not.
        """
        types = self.expand_varargs(len(values))

        mismatches = set()
        # By default, the varargs are matched. Only return that it is mismatched if
        # there is an explicit mismatch.
        varargs_matched = True

        for i, (v, t) in enumerate(zip(values, types)):
            if not _is_bearable(v, t):
                if i < len(self.types):
                    mismatches.add(i)
                else:
                    varargs_matched = False

        return mismatches, varargs_matched


def inspect_signature(f) -> inspect.Signature:
    """Wrapper of :func:`inspect.signature` which adds support for certain non-function
    objects.

    Args:
        f (object): Function-like object.

    Returns:
        object: Signature.
    """
    if isinstance(f, operator.itemgetter):
        f = wrap_lambda(f)
    elif isinstance(f, operator.attrgetter):
        f = wrap_lambda(f)
    return inspect.signature(f)


def resolve_pep563(f: Callable):
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


def _extract_signature(f: Callable, precedence: int = 0) -> Signature:
    """Extract the signature from a function.

    Args:
        f (function): Function to extract signature from.
        precedence (int, optional): Precedence of the method.

    Returns:
        :class:`.Signature`: Signature.
    """
    resolve_pep563(f)

    # Extract specification.
    sig = inspect_signature(f)

    # Get types of arguments.
    types = []
    varargs = Missing
    for arg in sig.parameters:
        p = sig.parameters[arg]

        # Parse and resolve annotation.
        if p.annotation is inspect.Parameter.empty:
            annotation = typing.Any
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
        if p.default is not inspect.Parameter.empty:
            if not _is_bearable(p.default, annotation):
                raise TypeError(
                    f"Default value `{p.default}` is not an instance "
                    f"of the annotated type `{repr_short(annotation)}`."
                )

    return types, varargs


def append_default_args(signature: Signature, f: Callable) -> List[Signature]:
    """Returns a list of signatures of function `f`, where those signatures are derived
    from the input arguments of `f` by treating every non-keyword-only argument with a
    default value as a keyword-only argument turn by turn.

    Args:
        f (function): Function to extract default arguments from.
        signature (:class:`.signature.Signature`): Signature of `f` from which to
            remove default arguments.

    Returns:
        list[:class:`.signature.Signature`]: list of signatures excluding from 0 to all
        default arguments.
    """
    # Extract specification.
    f_signature = inspect_signature(f)

    signatures = [signature]

    arg_names = list(f_signature.parameters.keys())
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
