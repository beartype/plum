import inspect
import operator
import typing
from typing import Callable, List, Optional, Tuple

import beartype.door
from beartype.peps import resolve_pep563

from . import _is_bearable
from .type import is_faithful, resolve_type_hint
from .util import Comparable, Missing, TypeHint, multihash, repr_short, wrap_lambda

__all__ = ["Signature", "extract_signature", "append_default_args"]


class Signature(Comparable):
    """Signature.

    Args:
        *types (tuple[type, ...]): Types of the arguments.
        varargs (type, optional): Type of the variable arguments.
        return_type (type, optional): Type of the return value. Defaults to `Any`.
        precedence (int, optional): Precedence. Default to `0`.
        implementation (function, optional): Implementation.

    Attributes:
        types (tuple[type, ...]): Types of the arguments.
        varargs (type or :class:`.util.Missing`): Type of the variable number of
            arguments.
        has_varargs (bool): Whether `varargs` is not :class:`.util.Missing`.
        return_type (type): Return type.
        precedence (int): Precedence.
        implementation (function or None): Implementation.
        is_faithful (bool): Whether this signature only uses faithful types.
    """

    _default_varargs = Missing
    _default_return_type = typing.Any
    _default_precedence = 0

    def __init__(
        self,
        *types: TypeHint,
        varargs=_default_varargs,
        return_type: TypeHint = _default_return_type,
        precedence: int = _default_precedence,
        implementation: Optional[Callable] = None,
    ):
        self.types: Tuple[TypeHint] = types
        self.varargs = varargs
        self.return_type = return_type
        self.precedence = precedence
        self.implementation = implementation

        types_are_faithful = all(is_faithful(t) for t in types)
        varargs_are_faithful = self.varargs is Missing or is_faithful(self.varargs)
        self.is_faithful = types_are_faithful and varargs_are_faithful

    @property
    def has_varargs(self) -> bool:
        return self.varargs is not Missing

    def __copy__(self):
        return Signature(
            *self.types,
            varargs=self.varargs,
            return_type=self.return_type,
            precedence=self.precedence,
            implementation=self.implementation,
        )

    def __repr__(self) -> str:
        parts = []
        if self.types:
            parts.append(", ".join(map(repr_short, self.types)))
        if self.varargs != Signature._default_varargs:
            parts.append("varargs=" + repr_short(self.varargs))
        if self.return_type != Signature._default_return_type:
            parts.append("return_type=" + repr_short(self.return_type))
        if self.precedence != Signature._default_precedence:
            parts.append("precedence=" + repr(self.precedence))
        if self.implementation:
            parts.append("implementation=" + repr(self.implementation))
        return "Signature(" + ", ".join(parts) + ")"

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


def _inspect_signature(f) -> inspect.Signature:
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


def extract_signature(f: Callable, precedence: int = 0) -> Signature:
    """Extract the signature from a function.

    Args:
        f (function): Function to extract signature from.
        precedence (int, optional): Precedence of the method.

    Returns:
        :class:`.Signature`: Signature.
    """
    if hasattr(f, "__annotations__"):
        resolve_pep563(f)  # This mutates `f`.
        # Override the `__annotations__` attribute, since `resolve_pep563` modifies
        # `f` too.
        for k, v in typing.get_type_hints(f).items():
            f.__annotations__[k] = v

    # Extract specification.
    sig = _inspect_signature(f)

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

    # Get possible return type.
    if sig.return_annotation is inspect.Parameter.empty:
        return_type = typing.Any
    else:
        return_type = resolve_type_hint(sig.return_annotation)

    # Assemble signature.
    signature = Signature(
        *types,
        varargs=varargs,
        return_type=return_type,
        precedence=precedence,
        implementation=f,
    )

    return signature


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
    f_signature = _inspect_signature(f)

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

        copy = signatures[-1].__copy__()

        # As specified over, these additional signatures should never have variable
        # arguments.
        copy.varargs = Missing

        # Remove the last positional argument.
        copy.types = copy.types[:-1]

        signatures.append(copy)

    return signatures
