import logging
import inspect
import builtins

from .function import Function, extract_signature
from .signature import Signature as Sig
from .type import subclasscheck_cache, Self, as_type

__all__ = ["Dispatcher", "dispatch", "clear_all_cache"]

log = logging.getLogger(__name__)


class _Undetermined:
    """Indication that an argument is yet undetermined."""


def _try_class_from_stack(up_extra=0):
    stack = inspect.stack()
    # Need to add one level if `__build_class__` is wrapped.
    num_back = up_extra + 3 + hasattr(builtins, "__build_class__")
    num_back_locals = up_extra + 1
    if (
        len(stack) >= num_back
        and stack[num_back - 1].code_context
        and stack[num_back - 1].code_context[0].strip().startswith("class")
    ):
        f_locals = stack[num_back_locals].frame.f_locals
        return Self(), f'{f_locals["__module__"]}.{f_locals["__qualname__"]}'
    else:
        return None, None


class Dispatcher:
    """A namespace for functions.

    Args:
        in_class (type or ptype, optional): Class to which the namespace is associated.
            If it not specified, it will attempt to determine whether we are in a
            class definition by inspecting the code context of two frames up in the
            stack.
    """

    def __init__(self, in_class=_Undetermined):
        self._functions = {}
        if in_class is _Undetermined:
            in_class, _ = _try_class_from_stack(up_extra=1)
        self._class = None if in_class is None else as_type(in_class)

    def _resolve_context_in_class(self, context, in_class):
        if context is _Undetermined:
            if self._class is None:
                # We might be in a class.
                _, context = _try_class_from_stack(up_extra=2)
            else:
                # Context not necessary, because the dispatcher was given a class.
                context = None

        if in_class is _Undetermined:
            if self._class is None:
                # We might be in a class.
                in_class, _ = _try_class_from_stack(up_extra=2)
            else:
                # The dispatcher was given a class.
                in_class = self._class
        return context, in_class

    def __call__(
        self, f=None, precedence=0, context=_Undetermined, in_class=_Undetermined
    ):
        """Decorator for a particular signature.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to `0`.

        Returns:
            function: Decorator.
        """
        context, in_class = self._resolve_context_in_class(context, in_class)

        # If `f` is not given, some keywords are set: return another decorator.
        if f is None:

            def decorator(f_):
                return self(
                    f_, precedence=precedence, context=context, in_class=in_class
                )

            return decorator

        signature, return_type = extract_signature(f)
        return self._add_method(
            f,
            [signature],
            precedence=precedence,
            return_type=return_type,
            context=context,
            in_class=in_class,
        )

    def multi(
        self,
        *signatures,
        precedence=0,
        return_type=object,
        context=_Undetermined,
        in_class=_Undetermined,
    ):
        """Create a decorator for multiple given signatures.

        Args:
            *signatures (tuple[type]): Signatures.
            precedence (int, optional): Precedence of the signatures. Defaults to `0`.
            return_type (type, optional): Expected return type. Defaults to `object.`

        Returns:
            function: Decorator.
        """
        context, in_class = self._resolve_context_in_class(context, in_class)

        def decorator(f):
            return self._add_method(
                f,
                [Sig(*types) for types in signatures],
                precedence=precedence,
                return_type=return_type,
                context=context,
                in_class=in_class,
            )

        return decorator

    def _add_method(self, f, signatures, precedence, return_type, context, in_class):
        # Set the name based on the context.
        if context:
            name = f"{context}.{f.__name__}"
        else:
            name = f.__name__

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
