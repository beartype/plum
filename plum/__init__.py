__all__ = (
    # Alias
    "activate_union_aliases",
    "deactivate_union_aliases",
    "set_union_alias",
    # Autoreload
    "activate_autoreload",
    "deactivate_autoreload",
    # Dispatcher
    "Dispatcher",
    "dispatch",
    "clear_all_cache",
    # Functions
    "Function",
    # Method
    "Method",
    "extract_return_type",
    # Overload
    "overload",  # TODO: deprecate
    "get_overloads",  # TODO: deprecate
    # Parametric
    "CovariantMeta",
    "parametric",
    "type_parameter",
    "type_nonparametric",
    "type_unparametrized",
    "kind",
    "Kind",
    # Promotion
    "convert",
    "add_conversion_method",
    "conversion_method",
    "add_promotion_rule",
    "promote",
    # Resolver
    "AmbiguousLookupError",
    "NotFoundLookupError",
    # Signature
    "Signature",
    "append_default_args",
    "inspect_signature",
    # Type
    "PromisedType",
    "ModuleType",
    "type_mapping",
    "resolve_type_hint",
    "is_faithful",
    # util
    "Callable",  # TODO: deprecate
    "TypeHint",
    "Missing",
    "Comparable",
    "wrap_lambda",
    "is_in_class",
    "get_class",
    "get_context",
    "argsort",
)

from typing import TypeGuard, TypeVar

from beartype.door import TypeHint as _TypeHint

from ._alias import activate_union_aliases, deactivate_union_aliases, set_union_alias
from ._autoreload import activate_autoreload, deactivate_autoreload
from ._bear import is_bearable as _is_bearable
from ._dispatcher import Dispatcher, clear_all_cache, dispatch
from ._function import Function
from ._method import Method, extract_return_type
from ._overload import get_overloads, overload
from ._parametric import (
    CovariantMeta,
    Kind,
    kind,
    parametric,
    type_nonparametric,
    type_parameter,
    type_unparametrized,
)
from ._promotion import (
    add_conversion_method,
    add_promotion_rule,
    conversion_method,
    convert,
    promote,
)
from ._resolver import AmbiguousLookupError, NotFoundLookupError
from ._signature import Signature, append_default_args, inspect_signature
from ._type import (
    ModuleType,
    PromisedType,
    is_faithful,
    resolve_type_hint,
    type_mapping,
)
from ._util import (
    Callable,
    Comparable,
    Missing,
    TypeHint,
    argsort,
    get_class,
    get_context,
    is_in_class,
    wrap_lambda,
)
from ._version import __version__  # noqa: F401  # noqa: F401

# isort: split
# Plum previously exported a number of types. As of recently, the user can use
# the versions from `typing`. To not break backward compatibility, we still
# export these types.
from typing import Dict, List, Tuple, Union  # noqa: F401, UP035

# Deprecated
# isort: split
from ._parametric import Val as Val  # noqa: F401, F403

T = TypeVar("T")
T2 = TypeVar("T2")


def isinstance(instance: object, c: type[T] | _TypeHint[T]) -> TypeGuard[T]:
    """Check if `instance` is of type or type hint `c`.

    This is a drop-in replace for the built-in :func:`isinstance` which supports
    type hints.

    Args:
        instance (object): Instance.
        c (type or object): Type or type hint.

    Returns:
        bool: Whether `instance` is of type or type hint `c`.
    """
    pred: bool = _is_bearable(instance, resolve_type_hint(c))
    return pred


def issubclass(
    c1: type[T] | _TypeHint[T], c2: type[T2] | _TypeHint[T2]
) -> TypeGuard[type[T2] | _TypeHint[T2]]:
    """Check if `c1` is a subclass or sub-type hint of `c2`.

    This is a drop-in replace for the built-in :func:`issubclass` which supports type
    hints.

    Args:
        c1 (type or object): First type or type hint.
        c2 (type or object): Second type or type hint.

    Returns:
        bool: Whether `c1` is a subtype or sub-type hint of `c2`.
    """
    pred: bool = _TypeHint(resolve_type_hint(c1)) <= _TypeHint(resolve_type_hint(c2))
    return pred
