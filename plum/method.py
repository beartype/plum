import inspect
import typing
from typing import Callable, Optional


from .signature import inspect_signature
from .type import resolve_type_hint
from .util import (
    TypeHint,
)
from .signature import Signature


class Method:
    """Method.

    Args:
        implementation (function): Callable implementing the function
        signature (Signature): Signature of the callable implementation.
        return_type (type, optional): Return type of the method. Can be left
            specified and the correct type will be deduced from the signature.
        return_type (type, optional): Type of the return value. Defaults to `Any`.

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
        if return_type is None:
            return_type = extract_return_type(implementation)
        if function_name is None:
            function_name = implementation.__name__

        self.implementation: Callable = implementation
        self.signature: Signature = signature

        self.function_name: str = function_name
        self.return_type: TypeHint = return_type

    def __copy__(self):
        return Method(
            self.implementation,
            self.signature,
            function_name=self.function_name,
            return_type=self.return_type,
        )

    def __eq__(self, othr):
        if isinstance(othr, Method):
            s = (
                self.function_name,
                self.implementation,
                self.signature,
                self.return_type,
            )
            o = (
                othr.function_name,
                othr.implementation,
                othr.signature,
                othr.return_type,
            )
            return s == o
        return False

    def __hash__(self):
        s = (self.function_name, self.implementation, self.signature, self.return_type)
        return hash(s)

    def __repr__(self):
        function_name = self.function_name
        signature = self.signature
        return_type = self.return_type
        impl = self.implementation
        return f"Method({function_name=}, {signature=}, {return_type=}, {impl=})"


def extract_return_type(f: Callable) -> TypeHint:
    """Extract the return type from a function.

    Args:
        f (function): Function to extract return type from.

    Returns:
        :class:`.TypeHint`: Return type annotation
    """
    # For all uses within plum right now, we are guaranteed to have already
    # resolved pep563 before in register.
    # signature.resolve_pep563(f)

    # Extract specification.
    sig = inspect_signature(f)

    # Get possible return type.
    if sig.return_annotation is inspect.Parameter.empty:
        return_type = typing.Any
    else:
        return_type = resolve_type_hint(sig.return_annotation)

    return return_type
