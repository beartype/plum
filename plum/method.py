import inspect
import typing
from typing import Callable, Optional

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

    def __repr__(self):
        function_name = self.function_name
        signature = self.signature
        return_type = self.return_type
        impl = self.implementation
        return f"Method({function_name=}, {signature=}, {return_type=}, {impl=})"


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
