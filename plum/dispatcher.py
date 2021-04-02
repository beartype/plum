import logging

from .function import Function, extract_signature
from .signature import Signature as Sig
from .type import subclasscheck_cache

__all__ = ["Dispatcher", "dispatch", "clear_all_cache"]

log = logging.getLogger(__name__)


class Dispatcher:
    """A namespace for functions.

    Args:
        in_class (type, optional): Class to which the namespace is associated.
    """

    def __init__(self, in_class=None):
        self._functions = {}
        self._class = in_class

    def __call__(self, f=None, precedence=0):
        """Decorator for a particular signature.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to `0`.

        Returns:
            function: Decorator.
        """
        if f is None:
            return lambda f_: self(f_, precedence=precedence)

        signature, return_type = extract_signature(f)
        return self._add_method(f, [signature], precedence, return_type)

    def multi(self, *signatures, precedence=0, return_type=object):
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
        name = f.__name__

        # Create a new function only if the function does not already exist.
        if name not in self._functions:
            self._functions[name] = Function(f, in_class=self._class)

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
