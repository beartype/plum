from .function import Function
from .signature import Signature
from .util import get_class, is_in_class

__all__ = ["Dispatcher", "dispatch", "clear_all_cache"]


class Dispatcher:
    """A namespace for functions.

    Attributes:
        functions (dict[str, :class:`.function.Function`]): Functions by name.
        classes (dict[str, dict[str, :class:`.function.Function`]]): Methods of
            all classes by the qualified name of a class.
    """

    def __init__(self):
        self.functions = {}
        self.classes = {}

    def __call__(self, method=None, precedence=0):
        """Decorator to register for a particular signature.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to `0`.

        Returns:
            function: Decorator.
        """
        if method is None:
            return lambda m: self(m, precedence=precedence)

        # The signature will be automatically derived from `method`, so we can safely
        # set the signature argument to `None`.
        return self._add_method(method, None, precedence=precedence)

    def multi(self, *signatures):
        """Decorator to register multiple signatures at once.

        Args:
            *signatures (tuple or :class:`.signature.Signature`): Signatures to
                register.

        Returns:
            function: Decorator.
        """
        resolved_signatures = []
        for signature in signatures:
            if isinstance(signature, Signature):
                resolved_signatures.append(signature)
            elif isinstance(signature, tuple):
                resolved_signatures.append(Signature(*signature))
            else:
                raise ValueError(
                    f"Signature `{signature}` must be a tuple or of type "
                    f"`plum.signature.Signature`."
                )

        def decorator(method):
            # The precedence will not be used, so we can safely set it to `None`.
            return self._add_method(method, *resolved_signatures, precedence=None)

        return decorator

    def abstract(self, method):
        """Decorator for an abstract function definition. The abstract function
        definition does not implement any methods."""
        return self._get_function(method)

    def _get_function(self, method):
        # If a class is the owner, use a namespace specific for that class. Otherwise,
        # use the global namespace.
        if is_in_class(method):
            owner = get_class(method)
            if owner not in self.classes:
                self.classes[owner] = {}
            namespace = self.classes[owner]
        else:
            owner = None
            namespace = self.functions

        # Create a new function only if the function does not already exist.
        name = method.__name__
        if name not in namespace:
            namespace[name] = Function(method, owner=owner)

        return namespace[name]

    def _add_method(self, method, *signatures, precedence):
        f = self._get_function(method)
        for signature in signatures:
            f.register(method, signature, precedence)
        return f

    def clear_cache(self):
        """Clear cache."""
        for f in self.functions.values():
            f.clear_cache()


def clear_all_cache():
    """Clear all cache, including the cache of subclass checks. This should be called
    if types are modified."""
    for f in Function._instances:
        f.clear_cache()


dispatch = Dispatcher()  #: A default dispatcher for convenience purposes.
