# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import logging
from functools import wraps

from .tuple import Tuple
from .type import as_type

__all__ = ['Function', 'AmbiguousLookupError', 'NotFoundLookupError']
log = logging.getLogger(__name__)


class AmbiguousLookupError(LookupError):
    """A signature cannot be resolved due to ambiguity."""


class NotFoundLookupError(LookupError):
    """A signature cannot be resolved because no applicable method can be
    found."""


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

        self._cache = {}
        self._class = as_type(in_class) if in_class else None

        self._pending = []
        self._resolved = []

        # Copy some basic info.
        self.__name__ = f.__name__
        self.__doc__ = f.__doc__

    def extend(self, *types, **kw_args):
        """A decorator to extend the function with another signature."""
        return self.extend_multi(types, **kw_args)

    def extend_multi(self, *signatures, **kw_args):
        """A decorator to extend the function with multiple signatures."""
        if 'precedence' in kw_args:
            precedence = kw_args['precedence']
        else:
            precedence = 0

        def decorator(f):
            # Register the new method.
            for signature in signatures:
                self.register(Tuple(*signature), f, precedence=precedence)

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

    def register(self, signature, f, precedence=0):
        """Register a method.

        Args:
            signature (:class:`.tuple.Tuple`): Signature of the method.
            f (function): Function that implements the method.
            precedence (int, optional): Precedence of the function. Defaults
                to `0`.
        """
        self._pending.append((signature, f, precedence))

    def _resolve_pending_registrations(self):
        registered = False

        # Perform any pending registrations.
        for signature, f, precedence in self._pending:
            registered = True

            # Check that a method with the same signature hasn't been defined
            # already.
            if signature in self.methods:
                raise RuntimeError('For function "{}", the method with '
                                   'signature {} has been defined multiple '
                                   'times.'.format(self._f.__name__, signature))

            log.debug('For function "{}", resolving registration with '
                      'signature {}.'.format(self._f.__name__, signature))
            self.methods[signature] = f
            self.precedences[signature] = precedence

            # Add to resolved registrations.
            self._resolved.append((signature, f, precedence))

        if registered:
            self._pending = []

            # Clear cache.
            # TODO: Do something more clever.
            self.clear_cache(reregister=False)

    def resolve(self, signature):
        """Resolve a signature.

        Args:
            signature (:class:`.tuple.Tuple`): Signature to resolve.

        Returns:
            The most-specific signature among the signatures of all applicable
            methods.
        """
        self._resolve_pending_registrations()

        # Find the most specific applicable signature.
        candidates = [s for s in self.methods.keys() if signature <= s]
        log.info('Applicable candidates: [{}].'
                 ''.format(', '.join(map(str, candidates))))
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

    def __call__(self, *args, **kw_args):
        self._resolve_pending_registrations()

        # Get types of arguments for signatures.
        sig_args = args[1:] if self._class else args  # Split off `self`.
        sig_types = tuple(type(x) for x in sig_args)

        # Attempt to use cache.
        try:
            return self._cache[sig_types](*args, **kw_args)
        except KeyError:
            pass

        # Look up the signature.
        signature = Tuple(*sig_types)

        if self._class:
            try:
                method = self.methods[self.resolve(signature)]
            except NotFoundLookupError as e:
                method = None

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
            method = self.methods[self.resolve(signature)]

        # Cache lookup.
        self._cache[sig_types] = method

        return method(*args, **kw_args)

    def __get__(self, instance, cls=None):
        # Prepend `instance` to the arguments in case the call is bound.
        prefix = () if instance is None else (instance,)

        # Wrap the function using `wraps` to preserve docstrings and such.
        # Also keep a newline here to prevent this comment being associated
        # to the wrapped function.

        @wraps(self._f)
        def f_wrapped(*args, **kw_args):
            return self(*(prefix + args), **kw_args)

        return f_wrapped

    def invoke(self, *types):
        return self.methods[self.resolve(Tuple(*types))]


def find_most_specific(signatures):
    """Find the most specific in a list of signatures.

     Args:
        signatures (list[:class:`.tuple.Tuple`]): List of signatures.

    Returns:
        :class:`.tuple.Tuple`: Most specific signatures.
    """
    candidates = []
    for signature in signatures:
        log.info('Iteration: candidates: [{}]; considering {}.'
                 ''.format(', '.join(map(str, candidates)), signature))

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

    log.info('Reduced to [{}].'.format(', '.join(map(str, candidates))))
    return candidates
