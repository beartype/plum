# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import logging

from plum.type import is_object

from .resolvable import Promise
from .signature import Signature
from .type import as_type, is_type
from .util import get_default

__all__ = ['Function', 'AmbiguousLookupError', 'NotFoundLookupError']
log = logging.getLogger(__name__)


class AmbiguousLookupError(LookupError):
    """A signature cannot be resolved due to ambiguity."""


class NotFoundLookupError(LookupError):
    """A signature cannot be resolved because no applicable method can be
    found."""


# These promises are necessary to avoid circular imports.
promised_convert = Promise()  # This will resolve to `.promotion.convert`.
promised_type_of = Promise()  # This will resolve to `.parametric.type_of`.


def _convert(obj, target_type):
    """Convert an object to a particular type. Converts if `target_type` is not
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


# This is a default instance of the Plum `object` type, which is used to
# speed up cached calls.
default_obj_type = as_type(object)


class WrappedMethod(object):
    """Wrap a method, copying metadata and handling bound and unbound calls and
    conversion to the right return type.

    Args:
        method (function): Method to wrap.
        instance (tuple, optional): Instance in the case of a bound call.
            Defaults to `None`.
        return_type (ptype, optional): Return type. Defaults to `object`.
    """

    def __init__(self, method, instance=None, return_type=default_obj_type):
        self._method = method
        self._instance = instance
        self._return_type = return_type

        # Copy metadata.
        self.__name__ = method.__name__
        self.__doc__ = method.__doc__
        self.__module__ = method.__module__

    def __call__(self, *args, **kw_args):
        if self._instance is not None:
            args = (self._instance,) + args

        # Optimise the common case that the return type is `object`.
        if self._return_type is default_obj_type:
            return self._method(*args, **kw_args)
        else:
            return _convert(self._method(*args, **kw_args), self._return_type)

    def __repr__(self):
        return repr(self._method)

    def invoke(self, *types):
        if self._instance is not None:
            types = (self._instance,) + types

        return self._method.invoke(*types)


class Function(object):
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
        self._class = as_type(in_class) if in_class else None

        self._pending = []
        self._resolved = []

        # Copy metadata.
        self.__name__ = f.__name__
        self.__doc__ = f.__doc__
        self.__module__ = f.__module__

    def extend(self, *types, **kw_args):
        """A decorator to extend the function with another signature."""
        return self.extend_multi(types, **kw_args)

    def extend_multi(self, *signatures, **kw_args):
        """A decorator to extend the function with multiple signatures."""
        precedence = get_default(kw_args, 'precedence', 0)
        return_type = get_default(kw_args, 'return_type', object)

        def decorator(f):
            # Register the new method.
            for signature in signatures:
                self.register(Signature(*signature),
                              f,
                              precedence=precedence,
                              return_type=return_type)

            # Return the function.
            return self

        return decorator

    def clear_cache(self, reregister=True):
        """Clear cache.

        Args:
            reregister (bool, optional): Also reregister all methods.
                Defaults to `True`.
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
            return_type (type, optional): Return type of the function. Defaults
                to `object`.
        """
        self._pending.append((signature, f, precedence, return_type))

    def _resolve_pending_registrations(self):
        registered = False

        # Perform any pending registrations.
        for signature, f, precedence, return_type in self._pending:
            registered = True

            # Check that a method with the same signature hasn't been defined
            # already.
            if signature in self.methods:
                raise RuntimeError('For function "{}", the method with '
                                   'signature {} has been defined multiple '
                                   'times.'.format(self._f.__name__, signature))

            # If the return type is `object`, then set it to `default_obj_type`.
            # This allows for a fast check to speed up cached calls.
            return_type = as_type(return_type)
            if is_object(return_type):
                return_type = default_obj_type

            # Make sure to convert return type to Plum type.
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
            # TODO: Do something more clever, but be careful with the tracking
            # of parametric types.
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
            listed_candidates = '\n  '.join(['{} (precedence: {})'
                                             ''.format(c, self.precedences[c])
                                             for c in candidates])
            raise AmbiguousLookupError(
                'For function "{}", signature {} is ambiguous among the '
                'following:\n  {}'.format(self._f.__name__, signature,
                                          listed_candidates))
        elif len(candidates) == 1:
            return candidates[0]
        else:
            class_message = ' of {}'.format(self._class) if self._class else ''
            raise NotFoundLookupError(
                'For function "{}"{}, signature {} could not be resolved.'
                ''.format(self._f.__name__, class_message, signature))

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
                method, return_type = \
                    self.methods[self.resolve_signature(signature)]
            except NotFoundLookupError as e:
                method = None
                return_type = as_type(object)

                # Walk through the classes in the class's MRO, except for this
                # class, and try to get the method.
                for c in self._class.mro()[1:]:
                    try:
                        method = getattr(c, self._f.__name__)
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
            method, return_type \
                = self.methods[self.resolve_signature(signature)]

        # Cache lookup.
        self._cache[types] = (method, return_type)
        return method, return_type

    def __call__(self, *args, **kw_args):
        # First resolve pending registrations, because the value of
        # `self._parametric` depends on it.
        if len(self._pending) != 0:
            self._resolve_pending_registrations()

        # Get types of arg.
        if self._class:
            sig_args = args[1:]
        else:
            sig_args = args

        # Get types of arguments for signature. Only use `type_of` if
        # necessary, because it incurs a significant performance hit.
        if not self._parametric:
            sig_types = tuple([type(x) for x in sig_args])
        else:
            sig_types = tuple([promised_type_of.resolve()(x) for x in sig_args])

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
        # Check whether the call is bound or unbound.
        bound = len(types) >= 1 and not is_type(types[0])

        # Split instance in the case of a bound call.
        instance, types = (types[0], types[1:]) if bound else (None, types)

        # Get method and return type, and perform call.
        method, return_type = self.resolve_method(*[as_type(t) for t in types])
        return WrappedMethod(method, instance=instance, return_type=return_type)

    def __get__(self, instance, cls=None):
        return WrappedMethod(self, instance=instance)

    def __repr__(self):
        return '<function {} with {} method(s)>' \
               ''.format(self._f, len(self._pending) + len(self._resolved))


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
