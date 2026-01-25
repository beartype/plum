import importlib.util
from typing import TypeGuard, TypeVar

from beartype.door import TypeHint as _TypeHint

from ._bear import is_bearable as _is_bearable
from ._type import *  # noqa: F401, F403
from ._type import resolve_type_hint
from ._version import __version__  # noqa: F401
from .alias import *  # noqa: F401, F403
from .autoreload import *  # noqa: F401, F403
from .dispatcher import *  # noqa: F401, F403
from .function import *  # noqa: F401, F403
from .method import *  # noqa: F401, F403
from .overload import *  # noqa: F401, F403
from .parametric import *  # noqa: F401, F403
from .promotion import *  # noqa: F401, F403
from .resolver import *  # noqa: F401, F403
from .signature import *  # noqa: F401, F403
from .util import *  # noqa: F401, F403

# Detect if we're running a mypyc-compiled version
# Check the dispatcher module since __init__ is not compiled
try:
    from . import dispatcher as _dispatcher_module  # noqa: F401

    _spec = importlib.util.find_spec("plum.dispatcher")
    COMPILED = (
        _spec is not None
        and _spec.origin is not None
        and _spec.origin.endswith((".pyd", ".so"))
    )
except Exception:
    COMPILED = False

# isort: split
# Plum previously exported a number of types. As of recently, the user can use
# the versions from `typing`. To not break backward compatibility, we still
# export these types.
from typing import Dict, List, Tuple, Union  # noqa: F401, UP035

# Deprecated
# isort: split
from .parametric import Val  # noqa: F401, F403

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
