import logging

from .function import Function, extract_signature
from .signature import Signature as Sig
from .type import subclasscheck_cache, ptype
from .util import is_in_class, get_class

__all__ = ["Dispatcher", "dispatch", "clear_all_cache"]

log = logging.getLogger(__name__)


class Dispatcher:
    """A namespace for functions."""

    def __init__(self):
        self._functions = {}

    def __call__(self, f=None, precedence=0):
        """Decorator for a particular signature.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to `0`.

        Returns:
            function: Decorator.
        """

        # If `f` is not given, some keywords are set: return another decorator.
        if f is None:

            def decorator(f_):
                return self(f_, precedence=precedence)

            return decorator

        signature, return_type = extract_signature(f)
        return self._add_method(
            f,
            [signature],
            precedence=precedence,
            return_type=return_type,
        )

    def multi(
        self,
        *signatures,
        precedence=0,
        return_type=object,
    ):
        """Create a decorator for multiple given signatures.

        Args:
            *signatures (tuple[type]): Signatures.
            precedence (int, optional): Precedence of the signatures. Defaults to `0`.
            return_type (type, optional): Expected return type. Defaults to `object.`

        Returns:
            function: Decorator.
        """

        def decorator(f):
            return self._add_method(
                f,
                [Sig(*types) for types in signatures],
                precedence=precedence,
                return_type=return_type,
            )

        return decorator

    def _add_method(self, f, signatures, precedence, return_type):
        if is_in_class(f):
            # The function is part of a class.
            name = f.__module__ + "." + f.__qualname__
            in_class = ptype(get_class(f))
        else:
            # The function is not part of a class. Use global namespace.
            name = f.__name__
            in_class = None

        # Create a new function only if the function does not already exist.
        if name not in self._functions:
            self._functions[name] = Function(f, in_class=in_class)

        # Register the new method.
        for signature in signatures:
            self._functions[name].register(signature, f, precedence, return_type)

        # Return the function.
        return self._functions[name]

    def clear_cache(self):
        """Clear cache."""
        for f in self._functions.values():
            f.clear_cache()


def clear_all_cache():
    """Clear all cache, including the cache of subclass checks. This
    should be called if types are modified."""
    # Clear function caches.
    for f in Function._instances:
        f.clear_cache()

    # Clear subclass check cache.
    subclasscheck_cache.clear()


dispatch = Dispatcher()  #: A default dispatcher for convenience purposes.
