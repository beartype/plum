from beartype.door import TypeHint as _TypeHint
from beartype.door import is_bearable as _is_bearable

from .autoreload import *  # noqa: F401, F403
from .dispatcher import *  # noqa: F401, F403
from .function import *  # noqa: F401, F403
from .parametric import *  # noqa: F401, F403
from .promotion import *  # noqa: F401, F403
from .resolver import *  # noqa: F401, F403
from .signature import *  # noqa: F401, F403
from .type import *  # noqa: F401, F403
from .type import resolve_type_hint
from .util import *  # noqa: F401, F403


def isinstance(instance, c):
    """Check if `instance` is of type or type hint `c`.

    This is a drop-in replace for the built-in :func:`ininstance` which supports type
    hints.

    Args:
        instance (object): Instance.
        c (type or object): Type or type hint.

    Returns:
        bool: Whether `instance` is of type or type hint `c`.
    """
    return _is_bearable(instance, resolve_type_hint(c))


def issubclass(c1, c2):
    """Check if `c1` is a subclass or sub-type hint of `c2`.

    This is a drop-in replace for the built-in :func:`issubclass` which supports type
    hints.

    Args:
        c1 (type or object): First type or type hint.
        c2 (type or object): First type or type hint.

    Returns:
        bool: Whether `c1` is a subtype or sub-type hint of `c2`.
    """
    return _TypeHint(resolve_type_hint(c1)) <= _TypeHint(resolve_type_hint(c2))
