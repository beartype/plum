# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import logging
import types
from functools import partial

from .tuple import Tuple
from .type import as_type

__all__ = ['Function', 'AmbiguousLookupError', 'NotFoundLookupError']
log = logging.getLogger(__name__)


class UnboundCall(object):
    """A special object to indicate an unbound call."""


class AmbiguousLookupError(LookupError):
    """A signature cannot be resolved due to ambiguity."""


class NotFoundLookupError(LookupError):
    """A signature cannot be resolved because no applicable method can be
    found."""


class Function(object):
    """A function.

    Args:
        name (string): Name of the function.
        in_class (type, optional): Class of which the function is part.
    """

    def __init__(self, name, in_class=None):
        self._name = name
        self.methods = {}
        self._cache = {}
        self._class = as_type(in_class) if in_class else None
        self._pending_signatures = []
        self._pending_fs = []

    def clear_cache(self):
        """Clear cache."""
        self._cache.clear()

    def register(self, signature, f):
        """Register a method.

        Args:
            signature (:class:`.tuple.Tuple`): Signature of the method.
            f (function): Function that implements the method.
        """
        self._pending_fs.append(f)
        self._pending_signatures.append(signature)

    def _resolve_pending_registrations(self):
        any_registered = False

        # Perform any pending registrations.
        for signature, f in zip(self._pending_signatures, self._pending_fs):
            any_registered = True

            # Check that a method with the same signature hasn't been defined
            # already.
            if signature in self.methods:
                raise RuntimeError('For function "{}", the method with '
                                   'signature {} has been defined multiple '
                                   'times.'.format(self._name, signature))

            log.debug('For function "{}", resolving registration with '
                      'signature {}.'.format(self._name, signature))
            self.methods[signature] = f

        if any_registered:
            self._pending_signatures, self._pending_fs = [], []

            # Clear cache.
            # TODO: Do something more clever.
            self.clear_cache()

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
        candidates = self.find_most_specific(candidates)

        # If only a single candidate is left, the resolution has been
        # successful.
        if len(candidates) > 1:
            raise AmbiguousLookupError(
                'For function "{}", signature {} is ambiguous among the '
                'following:\n  {}'.format(self._name, signature,
                                          '\n  '.join(map(str, candidates))))
        elif len(candidates) == 1:
            return candidates[0]
        else:
            raise NotFoundLookupError(
                'For function "{}", signature {} could not be resolved.'
                ''.format(self._name, signature))

    def __call__(self, *args, **kw_args):
        self._resolve_pending_registrations()

        # Handle unbound calls in the case of Python 3.
        if len(args) > 0 and args[0] is UnboundCall:
            args = args[1:]

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
                # class.
                for c in self._class.mro()[1:]:

                    # Get the function.
                    try:
                        f = getattr(c, self._name)
                    except AttributeError:
                        continue

                    # Get the method.
                    try:
                        if isinstance(f, Function):
                            method = f.methods[f.resolve(signature)]
                        else:
                            method = f
                        break
                    except NotFoundLookupError:
                        continue
                    except AmbiguousLookupError as e:
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
        try:
            # Python 2:
            return types.MethodType(self, instance, cls)
        except TypeError:
            # Python 3:
            if instance is None:
                return partial(self.__call__, UnboundCall)
            else:
                return partial(self.__call__, instance)

    @staticmethod
    def find_most_specific(signatures):
        """Find the most specific signatures in a list of signatures.

         Args:
            signatures (list of :class:`.tuple.Tuple`): List of signatures.
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
