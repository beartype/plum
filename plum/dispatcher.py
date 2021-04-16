import logging

from .function import ClassFunction, Function, extract_signature
from .signature import Signature as Sig
from .type import subclasscheck_cache
from .util import is_in_class, get_class

__all__ = ["Dispatcher", "dispatch", "clear_all_cache"]

log = logging.getLogger(__name__)


class Dispatcher:
    """A namespace for functions."""

    def __init__(self):
        self._functions = {}
        self._classes = {}

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

        def construct_function(owner):
            return self._add_method(
                f,
                [signature],
                precedence=precedence,
                return_type=return_type,
                owner=owner,
            )

        # Defer the construction if `f` is in a class. We defer the construct to allow
        # the function to hold a reference to the class.
        if is_in_class(f):
            return ClassFunction(get_class(f), construct_function)
        else:
            return construct_function(None)

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
        signatures = [Sig(*types) for types in signatures]

        def decorator(f):
            def construct_function(owner):
                return self._add_method(
                    f,
                    signatures,
                    precedence=precedence,
                    return_type=return_type,
                    owner=owner,
                )

            # Defer the construction if `f` is in a class. We defer the construct to
            # allow the function to hold a reference to the class.
            if is_in_class(f):
                return ClassFunction(get_class(f), construct_function)
            else:
                return construct_function(None)

        return decorator

    def _add_method(self, f, signatures, precedence, return_type, owner):
        name = f.__name__

        # If a class is the owner, use a namespace specific for that class.
        # Otherwise, use the global namespace.
        if owner:
            if owner not in self._classes:
                self._classes[owner] = {}
            namespace = self._classes[owner]
        else:
            namespace = self._functions

        # Create a new function only if the function does not already exist.
        if name not in namespace:
            namespace[name] = Function(f, owner=owner)

        # Register the new method.
        for signature in signatures:
            namespace[name].register(signature, f, precedence, return_type)

        # Return the function.
        return namespace[name]

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
