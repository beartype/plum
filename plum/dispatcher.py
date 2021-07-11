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

    def __call__(self, method=None, precedence=0):
        """Decorator for a particular signature.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to `0`.

        Returns:
            function: Decorator.
        """

        # If `method` is not given, some keywords are set: return another decorator.
        if method is None:

            def decorator(f_):
                return self(f_, precedence=precedence)

            return decorator

        signature, return_type = extract_signature(method)

        def construct_function(owner):
            return self._add_method(
                method,
                [signature],
                precedence=precedence,
                return_type=return_type,
                owner=owner,
            )

        # Defer the construction if `method` is in a class. We defer the construction to
        # allow the function to hold a reference to the class.
        if is_in_class(method):
            return ClassFunction(get_class(method), construct_function)
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

        def decorator(method):
            def construct_function(owner):
                return self._add_method(
                    method,
                    signatures,
                    precedence=precedence,
                    return_type=return_type,
                    owner=owner,
                )

            # Defer the construction if `method` is in a class. We defer the
            # construction to allow the function to hold a reference to the class.
            if is_in_class(method):
                return ClassFunction(get_class(method), construct_function)
            else:
                return construct_function(None)

        return decorator

    def abstract(self, method):
        """Decorator for an abstract function definition. The abstract function
        definition does not implement any methods."""

        def construct_abstract_function(owner):
            return self._get_function(method, owner)

        # Defer the construction if `method` is in a class. We defer the construction to
        # allow the function to hold a reference to the class.
        if is_in_class(method):
            return ClassFunction(get_class(method), construct_abstract_function)
        else:
            return construct_abstract_function(None)

    def _get_function(self, method, owner):
        name = method.__name__

        # If a class is the owner, use a namespace specific for that class. Otherwise,
        # use the global namespace.
        if owner:
            if owner not in self._classes:
                self._classes[owner] = {}
            namespace = self._classes[owner]
        else:
            namespace = self._functions

        # Create a new function only if the function does not already exist.
        if name not in namespace:
            namespace[name] = Function(method, owner=owner)

        return namespace[name]

    def _add_method(self, method, signatures, precedence, return_type, owner):
        f = self._get_function(method, owner)
        for signature in signatures:
            f.register(signature, method, precedence, return_type)
        return f

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
