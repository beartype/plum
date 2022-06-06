import abc
import logging

__all__ = [
    "wrap_lambda",
    "multihash",
    "Comparable",
    "is_in_class",
    "get_class",
    "get_context",
    "check_future_annotations",
    "unquote",
]

log = logging.getLogger(__name__)


def wrap_lambda(f):
    """Wrap a function in a lambda function.

    Args:
        f (function): Function to wrap.

    Returns:
        function: Wrapped version of `f`.
    """
    return lambda x: f(x)


def multihash(*args):
    """Multi-argument order-sensitive hash.

    Args:
        *args: Objects to hash.

    Returns:
        int: Hash.
    """
    return hash(args)


class Comparable:
    """A mixin that makes instances of the class comparable.

    Requires the subclass to just implement `__le__`.
    """

    __metaclass__ = abc.ABCMeta

    def __eq__(self, other):
        return self <= other <= self

    def __ne__(self, other):
        return not self == other

    @abc.abstractmethod
    def __le__(self, other):
        pass  # pragma: no cover

    def __lt__(self, other):
        return self <= other and self != other

    def __ge__(self, other):
        return other.__le__(self)

    def __gt__(self, other):
        return self >= other and self != other

    def is_comparable(self, other):
        """Check whether this object is comparable with another one.

        Args:
            other (:class:`.util.Comparable`): Object to check comparability
                with.

        Returns:
            bool: `True` if the object is comparable with `other` and `False`
                otherwise.
        """
        return self < other or self == other or self > other


def is_in_class(f):
    """Check if a function is part of a class.

    Args:
        f (function): Function to check.

    Returns:
        bool: `True` if `f` is part of a class, else `False`.
    """
    parts = f.__qualname__.split(".")
    return len(parts) >= 2 and parts[-2] != "<locals>"


def _split_parts(f):
    qualified_name = f.__module__ + "." + f.__qualname__
    return qualified_name.split(".")


def get_class(f):
    """Assuming that `f` is part of a class, get the fully qualified name of the
    class.

    Args:
        f (function): Method to get class name for.

    Returns:
        str: Fully qualified name of class.
    """
    parts = _split_parts(f)
    return ".".join(parts[:-1])


def get_context(f):
    """Get the fully qualified name of the context for `f`.

    If `f` is part of a class, then the context corresponds to the scope of the class.
    If `f` is not part of a class, then the context corresponds to the scope of the
    function.

    Args:
        f (function): Method to get context for.

    Returns:
        str: Context.
    """
    parts = _split_parts(f)
    if is_in_class(f):
        # Split off function name and class.
        return ".".join(parts[:-2])
    else:
        # Split off function name only.
        return ".".join(parts[:-1])


def check_future_annotations(frame=None):
    """Check if `from __future__ import annotations` is active in a frame.

    Args:
        frame (object): Frame.

    Returns:
        bool: `True` if it is activated, otherwise `False`.
    """
    return "annotations" in frame.f_globals


def unquote(x):
    """Remove quotes from a string at the outermost level.

    If `x` is not a string, `x` is returned immediately.

    Args:
        x (str or object): String to remove quotes from.

    Return:
        str or object: `x` but without quotes.
    """
    if not isinstance(x, str):
        return x
    while len(x) >= 2 and x[0] == x[-1] and x[0] in {'"', "'"}:
        x = x[1:-1]
    return x
