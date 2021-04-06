import inspect
import logging
from functools import wraps

from .resolvable import Promise
from .signature import Signature
from .type import ptype, is_object, VarArgs, deliver_reference

__all__ = [
    "extract_signature",
    "AmbiguousLookupError",
    "NotFoundLookupError",
    "promised_convert",
    "promised_type_of",
    "Function"
]

log = logging.getLogger(__name__)


# This is a default instance of the Plum `object` type, which is used to speed up
# cached calls.
default_obj_type = ptype(object)


def extract_signature(f):
    """Extract the signature from a function.

    Args:
        f (function): Function to extract signature from.

    Returns:
        tuple[:class:`.signature.Signature`, ptype]: Signature and return type of the
            function.
    """
    # Extract specification.
    spec = inspect.getfullargspec(f)

    # Get types of arguments. We need to already convert the types with `as_type` to
    # convert types given as strings in the context of the function to their fully
    # qualified names.
    types = []
    # Cut off keyword arguments: arguments which are given a default value.
    num_defaults = len(spec.defaults) if spec.defaults else 0
    for arg in spec.args[: len(spec.args) - num_defaults]:
        try:
            types.append(ptype(spec.annotations[arg], context=f))
        except KeyError:
            types.append(default_obj_type)

    # Get possible varargs.
    if spec.varargs:
        try:
            types.append(VarArgs(ptype(spec.annotations[spec.varargs], context=f)))
        except KeyError:
            types.append(VarArgs(default_obj_type))

    # Get possible return type.
    try:
        return_type = ptype(spec.annotations["return"], context=f)
    except KeyError:
        return_type = default_obj_type

    # Assemble signature.
    signature = Signature(*types)

    return signature, return_type


class AmbiguousLookupError(LookupError):
    """A signature cannot be resolved due to ambiguity."""


class NotFoundLookupError(LookupError):
    """A signature cannot be resolved because no applicable method can be found."""


# These promises are necessary to avoid circular imports.
promised_convert = Promise()  # This will resolve to `.promotion.convert`.
promised_type_of = Promise()  # This will resolve to `.parametric.type_of`.


def _convert(obj, target_type):
    """Convert an object to a particular type. Only converts if `target_type` is not
    `object`.

    Args:
        obj (object): Object to convert.
        target_type (type): Type to convert to.

    Returns:
        object: `object_to_covert` converted to type of `obj_from_target`.
    """
    if target_type is default_obj_type or is_object(target_type):
        return obj
    else:
        return promised_convert.resolve()(obj, target_type)


class Function:
    """A function.

    Args:
        f (function): Function that is wrapped.
        in_class (type, optional): Class of which the function is part.
    """

    _instances = []

    def __init__(self, f, in_class=None):
        Function._instances.append(self)

        self._f = f
        self.methods = {}
        self.precedences = {}

        # Keep track of whether any of the signatures contains a parametric
        # type. This is a necessary performance optimisation.
        self._parametric = False

        self._cache = {}
        self._class = ptype(in_class) if in_class else None

        self._pending = []
        self._resolved = []

        # Copy metadata.
        self.__name__ = f.__name__
        self.__doc__ = f.__doc__
        self.__module__ = f.__module__

    def extend(self, f=None, precedence=0):
        """A decorator to extend the function with another signature.

        Args:
            precedence (int, optional): Precedence of the signature. Defaults to `0`.

        Returns:
            function: Decorator.
        """
        if f is None:
            return lambda f_: self.extend(f_, precedence=precedence)

        signature, return_type = extract_signature(f)
        return self.extend_multi(
            signature, precedence=precedence, return_type=return_type
        )(f)

    def extend_multi(self, *signatures, precedence=0, return_type=object):
        """A decorator to extend the function with multiple signatures.

        Args:
            *signatures (tuple[type] or :class:`.signature.Signature`): Signatures.
            precedence (int, optional): Precedence of the signatures. Defaults to `0`.
            return_type (type, optional): Expected return type. Defaults to `object.`

        Returns:
            function: Decorator.
        """

        def decorator(f):
            # Register the new method.
            for signature in signatures:
                if not isinstance(signature, Signature):
                    signature = Signature(*signature)
                self.register(
                    signature, f, precedence=precedence, return_type=return_type
                )

            # Return the function.
            return self

        return decorator

    def clear_cache(self, reregister=True):
        """Clear cache.

        Args:
            reregister (bool, optional): Also reregister all methods. Defaults to
                `True`.
        """
        self._cache.clear()
        if reregister:
            # Add all resolved to pending.
            self._pending.extend(self._resolved)

            # Clear resolved.
            self._resolved = []
            self.methods.clear()
            self.precedences.clear()
            self._parametric = False

    def register(self, signature, f, precedence=0, return_type=object):
        """Register a method.

        Args:
            signature (:class:`.signature.Signature`): Signature of the method.
            f (function): Function that implements the method.
            precedence (int, optional): Precedence of the function. Defaults
                to `0`.
            return_type (type or ptype, optional): Return type of the function. Defaults
                to `object`.
        """
        # The return type may contain strings, which need to be converted Plum types
        # in the context of `f`.
        self._pending.append(
            (signature, f, precedence, ptype(return_type, context=f))
        )

    def _resolve_pending_registrations(self):
        # Keep track of whether anything registered.
        registered = False

        # Perform any pending registrations.
        for signature, f, precedence, return_type in self._pending:
            registered = True

            # If a method with the same signature has already been defined, then that
            # is fine: we simply overwrite that method.

            # If the return type is `object`, then set it to `default_obj_type`. This
            # allows for a fast check to speed up cached calls.
            if is_object(return_type):
                return_type = default_obj_type

            self.methods[signature] = (f, return_type)
            self.precedences[signature] = precedence

            # Add to resolved registrations.
            self._resolved.append((signature, f, precedence, return_type))

            # Check whether the signature contains a parametric type.
            if any(t.parametric for t in signature.types):
                self._parametric = True

        if registered:
            self._pending = []

            # Clear cache.
            # TODO: Be more clever, but careful about the tracking of parametric types.
            self.clear_cache(reregister=False)

    def resolve_signature(self, signature):
        """Resolve a signature to get the most specific signature amongst the
        signatures of all applicable methods.

        Args:
            signature (:class:`.signature.Signature`): Signature to resolve.

        Returns:
            :class:`.signature.Signature`: The most specific signature among the
                signatures of all applicable methods.
        """
        self._resolve_pending_registrations()

        # Find the most specific applicable signature.
        candidates = [s for s in self.methods.keys() if signature <= s]
        candidates = find_most_specific(candidates)

        # If only a single candidate is left, the resolution has been
        # successful.
        if len(candidates) > 1:
            # There are multiple candidates. Check their precedences and see
            # if that breaks the ambiguity.
            precedences = [self.precedences[c] for c in candidates]
            highest_precedence = max(*precedences)
            if len([p for p in precedences if p == highest_precedence]) == 1:
                # Ambiguity can be resolved by precedence. So do so.
                return candidates[precedences.index(highest_precedence)]

            # Could not resolve the ambiguity, so error. First, make a nice list
            # of the candidates and their precedences.
            listed_candidates = "\n  ".join(
                [f"{c} (precedence: {self.precedences[c]})" for c in candidates]
            )
            raise AmbiguousLookupError(
                f'For function "{self._f.__name__}", signature {signature} is '
                f"ambiguous among the following:\n  {listed_candidates}"
            )
        elif len(candidates) == 1:
            return candidates[0]
        else:
            class_message = f" of {self._class}" if self._class else ""
            raise NotFoundLookupError(
                f'For function "{self._f.__name__}"{class_message}, '
                f"signature {signature} could not be resolved."
            )

    def resolve_method(self, *types):
        """Get the method and return type corresponding to types of arguments.

        Args:
            *types (type): Types of arguments.

        Returns:
            tuple: Tuple containing method and return type.
        """
        # New registrations may invalidate cache, so resolve pending
        # registrations first.
        self._resolve_pending_registrations()

        # Attempt to use cache.
        try:
            return self._cache[types]
        except KeyError:
            pass

        # Look up the signature.
        signature = Signature(*types)

        if self._class:
            try:
                method, return_type = self.methods[self.resolve_signature(signature)]
            except NotFoundLookupError as e:
                method = None
                return_type = ptype(object)

                # Walk through the classes in the class's MRO, except for this
                # class, and try to get the method.
                for c in self._class.mro()[1:]:
                    try:
                        method = getattr(c, self._f.__name__)

                        # Ignore abstract methods.
                        if (
                            hasattr(method, "__isabstractmethod__")
                            and method.__isabstractmethod__
                        ):
                            method = None
                            continue

                        # We found a good candidate. Break.
                        break
                    except AttributeError:
                        pass

                if method == object.__init__:
                    # The constructor of `object` has been found. This
                    # happens when there a constructor is called and no
                    # appropriate method can be found. Raise the original
                    # exception.
                    raise e

                if not method:
                    # If no method has been found after walking through the
                    # MRO, raise the original exception.
                    raise e
        else:
            # Not in a class. Simply resolve.
            method, return_type = self.methods[self.resolve_signature(signature)]

        # Cache lookup.
        self._cache[types] = (method, return_type)
        return method, return_type

    def __call__(self, *args, **kw_args):
        # First resolve pending registrations, because the value of
        # `self._parametric` depends on it.
        if len(self._pending) != 0:
            self._resolve_pending_registrations()

        # Get types of arguments for signature. Only use `type_of` if
        # necessary, because it incurs a significant performance hit.
        if not self._parametric:
            sig_types = tuple([type(x) for x in args])
        else:
            sig_types = tuple([promised_type_of.resolve()(x) for x in args])

        try:
            # Attempt to use cache. This will also be done in
            # `self.resolve_method`, but checking here as well speed up
            # cached calls significantly.
            method, return_type = self._cache[sig_types]

            # Check for the common case that the return type is object. This is
            # to speed up the common case.
            if return_type is default_obj_type:
                return method(*args, **kw_args)
            else:
                return _convert(method(*args, **kw_args), return_type)
        except KeyError:
            pass

        # Cache failed. Get method and return type, and perform call.
        method, return_type = self.resolve_method(*sig_types)
        return _convert(method(*args, **kw_args), return_type)

    def invoke(self, *types):
        """Invoke a particular method.

        Args:
            *types: Types to resolve.

        Returns:
            function: Method.
        """
        method, return_type = self.resolve_method(*[ptype(t) for t in types])

        @wraps(self._f)
        def wrapped_method(*args, **kw_args):
            return _convert(method(*args, **kw_args), return_type)

        return wrapped_method

    def __get__(self, instance, owner):
        # Critical! This is the moment to deliver references.
        deliver_reference(owner)
        if instance:
            return _BoundFunction(self, instance)
        else:
            return self

    def __repr__(self):
        return (
            f"<function {self._f} with "
            f"{len(self._pending) + len(self._resolved)} method(s)>"
        )


class _BoundFunction:
    """A bound instance of `.function.Function`.

    Args:
        f (:class:`.function.Function`): Bound function.
        instance (object): Instance to which the function is bound.
    """

    def __init__(self, f, instance):
        self.f = f
        self.instance = instance

        # Copy relevant metadata.
        self.__name__ = f.__name__
        self.__module__ = f.__module__
        self.__doc__ = f.__doc__

    def __call__(self, *args, **kw_args):
        return self.f(self.instance, *args, **kw_args)

    def invoke(self, *types):
        """See :meth:`.function.invoke`."""

        @wraps(self.f._f)
        def wrapped_method(*args, **kw_args):
            return self.f.invoke(type(self.instance), *types)(
                self.instance, *args, **kw_args
            )

        return wrapped_method

    def __repr__(self):
        return repr(self.f)


def find_most_specific(signatures):
    """Find the most specific in a list of signatures.

     Args:
        signatures (list[:class:`.signature.Signature`]): List of signatures.

    Returns:
        :class:`.signature.Signature`: Most specific signatures.
    """
    candidates = []
    for signature in signatures:
        # If none of the candidates are comparable, then add the method as
        # a new candidate and continue.
        if not any(c.is_comparable(signature) for c in candidates):
            candidates += [signature]
            continue

        # The signature under consideration is comparable with at least one
        # of the candidates. First, filter any strictly more general
        # candidates.
        new_candidates = [c for c in candidates if not signature < c]

        # If the signature under consideration is as specific as at least
        # one candidate, then and only then add it as a candidate.
        if any(signature <= c for c in candidates):
            candidates = new_candidates + [signature]
        else:
            candidates = new_candidates

    return candidates
