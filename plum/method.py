import inspect
import typing
from typing import Callable, List, Optional, Set, Tuple

from rich.padding import Padding
from rich.text import Text

from .repr import repr_pyfunction, repr_type, rich_repr
from .signature import Signature, inspect_signature
from .type import resolve_type_hint
from .util import TypeHint

__all__ = ["Method", "extract_return_type"]


@rich_repr
class Method:
    """Method.

    Attributes:
        return_type (type): Return type.
        implementation (function or None): Implementation.
    """

    _default_return_type = typing.Any

    __slots__ = ("function_name", "implementation", "signature", "return_type")

    def __init__(
        self,
        implementation: Callable,
        signature: Signature,
        *,
        function_name: Optional[str] = None,
        return_type: Optional[TypeHint] = None,
    ):
        """Instantiate a method.

        Args:
            implementation (function): Callable implementing the method.
            signature (:class:`Signature`): Signature of the method.
            return_type (type, optional): Return type of the method. Can be left
                unspecified, in which case the correct type will be deduced from the
                signature.
            return_type (type, optional): Type of the return value. Defaults to
                :obj:`Any`.
        """
        if return_type is None:
            return_type = extract_return_type(implementation)
        if function_name is None:
            function_name = implementation.__name__

        self.implementation = implementation
        self.signature = signature
        self.function_name = function_name
        self.return_type = return_type

    def __copy__(self):
        return Method(
            self.implementation,
            self.signature,
            function_name=self.function_name,
            return_type=self.return_type,
        )

    def __eq__(self, other):
        if isinstance(other, Method):
            return (
                self.function_name,
                self.implementation,
                self.signature,
                self.return_type,
            ) == (
                other.function_name,
                other.implementation,
                other.signature,
                other.return_type,
            )
        return False

    def __hash__(self):
        s = (self.function_name, self.implementation, self.signature, self.return_type)
        return hash(s)

    def __str__(self):
        function_name = self.function_name
        signature = self.signature
        return_type = self.return_type
        impl = self.implementation
        return f"Method({function_name=}, {signature=}, {return_type=}, {impl=})"

    def __rich_console__(self, console, options):
        yield self.repr_mismatch()

    def repr_mismatch(
        self,
        mismatches: Set[int] = frozenset(),
        varargs_matched: bool = True,
    ) -> str:
        """Version of `__repr__` that can print which arguments are mismatched. This
        is mainly used in hints.

        Args:
            mismatches (set[int], optional): Indices of the positional arguments which
                are mismatched. Defaults to no mismatched arguments.
            varargs_matched (bool, optional): Whether the varargs are matched. Defaults
                to `True`.

        Returns:
            list:
                :mod:`rich` representation of the method showing which arguments
                are mismatched.
        """
        sig = self.signature
        arg_names, kw_names, kw_var_name = extract_arg_names(self.implementation)

        parts = []

        # Walk through the positional arguments.
        if sig.types:
            for i, (arg_name, t) in enumerate(zip(arg_names, sig.types)):
                arg_txt = Text(f"{arg_name}: ")
                type_txt = repr_type(t)
                if i in mismatches:
                    type_txt.stylize("red")
                arg_txt.append(type_txt)
                parts.append(arg_txt)

        # Print the varargs.
        if sig.varargs != Signature._default_varargs:
            arg_txt = Text(f"*{arg_names[-1]}: ")
            type_txt = repr_type(sig.varargs)
            if not varargs_matched:
                type_txt.stylize("red")
            arg_txt.append(type_txt)
            parts.append(arg_txt)

        if kw_names or kw_var_name is not None:
            parts.append(Text("*"))
        for kw_name in kw_names:
            parts.append(Text(f"{kw_name}"))
        if kw_var_name is not None:
            parts.append(Text(f"**{kw_var_name}"))

        res = Text(self.function_name) + Text("(") + Text(", ").join(parts) + Text(")")
        if self.return_type != Method._default_return_type:
            res.append(" -> ")
            res.append(repr_type(self.return_type))
        if sig.precedence != Signature._default_precedence:
            res.append(f"\n    precedence={sig.precedence}")

        res.append("\n    ")
        res.append_text(repr_pyfunction(self.implementation))

        return res


@rich_repr
class MethodList(list):
    "A list of :class:`Method`s which is nicely printed by :mod:`rich`."

    def __rich_console__(self, console, options):
        yield f"List of {len(self)} method(s):"
        for i, method in enumerate(self):
            method_repr = method.__rich_console__(console, options)
            yield Padding(sum(method_repr, Text(f"[{i}] ")), (0, 4))


def extract_arg_names(f: Callable) -> Tuple[List[str], List[str], Optional[str]]:
    """Extract the argument names for a function.

    Args:
        f (function): Function.

    Returns:
        list[str]: Regular arguments.
        list[str]: Keyword-only arguments.
        Optional[str]: The name of the splatted keyword argument, e.g.
            `**kw_args`.
    """
    # Extract specification.
    sig = inspect_signature(f)

    # Get types of arguments.
    regular_args = []
    kw_only_args = []
    var_kw_name = None
    for arg in sig.parameters:
        p = sig.parameters[arg]

        if p.kind == p.KEYWORD_ONLY:
            kw_only_args.append(p.name)
        elif p.kind == p.VAR_KEYWORD:
            var_kw_name = p.name
        else:
            regular_args.append(p.name)

    return regular_args, kw_only_args, var_kw_name


def extract_return_type(f: Callable) -> TypeHint:
    """Extract the return type from a function.

    Assumes that PEP563-style already have been resolved.

    Args:
        f (function): Function to extract return type from.

    Returns:
        :class:`TypeHint`: Return type annotation
    """

    # Extract specification.
    sig = inspect_signature(f)

    # Get possible return type.
    if sig.return_annotation is inspect.Parameter.empty:
        return_type = typing.Any
    else:
        return_type = resolve_type_hint(sig.return_annotation)

    return return_type
