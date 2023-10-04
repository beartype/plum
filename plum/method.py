import inspect
import typing
from typing import Callable, List, Optional

from .repr import color, colored, link, repr_type
from .signature import Signature, inspect_signature
from .type import resolve_type_hint
from .util import TypeHint

__all__ = ["Method", "extract_return_type"]


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

    def __repr__(self):
        argnames, kwnames, kwvar_name = extract_argnames(self.implementation)

        sig = self.signature
        parts = []
        if sig.types:
            for nm, t in zip(argnames, sig.types):
                parts.append(f"{nm}: {repr_type(t)}")
        if sig.varargs != Signature._default_varargs:
            parts.append(f"*{argnames[-1]}: {repr_type(sig.varargs)}")

        if len(kwnames) > 0 or kwvar_name is not None:
            parts.append("*")
        for kwnm in kwnames:
            parts.append(f"{kwnm}")
        if kwvar_name is not None:
            parts.append(f"**{kwvar_name}")

        res = f"{self.function_name}(" + ", ".join(parts) + ")"
        if self.return_type != Method._default_return_type:
            res += f" -> {repr_type(self.return_type)}"
        if sig.precedence != Signature._default_precedence:
            res += "\n\tprecedence=" + repr(sig.precedence)

        res += "\n\t" + self._repr_method_namepath()

        return res

    def _repr_method_namepath(self) -> str:
        """Returns the string with the link to the
        file and line where the method implementation
        is defined.
        """
        res = repr(self.implementation)
        try:
            fpath = inspect.getfile(self.implementation)
            fline = str(inspect.getsourcelines(self.implementation)[1])
            uri = "file://" + fpath + "#" + fline

            import os

            # compress the path
            home_path = os.path.expanduser("~")
            fpath = fpath.replace(home_path, "~")

            # underline file name
            fname = os.path.basename(fpath)
            if fname.endswith(".py"):
                fpath = fpath.replace(
                    fname, colored(colored(fname, color.BOLD), color.UNDERLINE)
                )
            fpath = fpath + ":" + fline

            res += " @ " + link(uri, fpath)
        except OSError:
            res = ""
        return res

    def _repr_signature_mismatch(self, args_ok: List[bool]) -> str:
        """Special version of __repr__ but used when
        printing args mismatch (mainly in hints to possible
        similar signatures).

        Args:
            args_ok: a list of which arguments match this signature
                and which don't according to the resolver.
        """
        sig = self.signature

        argnames, kwnames, kwvar_name = extract_argnames(self.implementation)
        varargs_ok = all(args_ok[len(sig.types) :])

        parts = []
        if sig.types:
            for i, (nm, t) in enumerate(zip(argnames, sig.types)):
                is_ok = args_ok[i] if i < len(args_ok) else False
                clr = (color.RED,) if not is_ok else tuple()
                parts.append(f"{nm}: {repr_type(t, *clr)}")
        if sig.varargs != Signature._default_varargs:
            clr = (color.RED,) if not varargs_ok else tuple()
            parts.append(f"*{argnames[-1]}: {repr_type(sig.varargs, *clr)}")

        if len(kwnames) > 0 or kwvar_name is not None:
            parts.append("*")
        for kwnm in kwnames:
            parts.append(f"{kwnm}")
        if kwvar_name is not None:
            parts.append(f"**{kwvar_name}")

        res = f"{self.function_name}(" + ", ".join(parts) + ")"
        if self.return_type != Method._default_return_type:
            res += f" -> {repr_type(self.return_type)}"
        if sig.precedence != Signature._default_precedence:
            res += "\n\tprecedence=" + repr(sig.precedence)

        res += "\n\t" + self._repr_method_namepath()

        return res


class MethodList(list):
    def __repr__(self):
        res = f"Method List with # {len(self)} methods:"
        for i, method in enumerate(self):
            res += f"\n [{i}] " + repr(method)
        return res


def extract_argnames(f: Callable, precedence: int = 0) -> Signature:
    """Extract the signature from a function.

    Args:
        f (function): Function to extract signature from.
        precedence (int, optional): Precedence of the method.

    Returns:
        :class:`.Signature`: Signature.
    """
    # Extract specification.
    sig = inspect_signature(f)

    # Get types of arguments.
    argnames = []
    kwnames = []
    kwvar_name = None
    for arg in sig.parameters:
        p = sig.parameters[arg]

        if p.kind in {p.KEYWORD_ONLY}:
            kwnames.append(p.name)
        elif p.kind in {p.VAR_KEYWORD}:
            kwvar_name = p.name
        else:
            argnames.append(p.name)

    return argnames, kwnames, kwvar_name


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
