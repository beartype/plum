from typing import Callable, Iterable, List, Optional, Tuple, Union

from plum.signature import Signature
from plum.type import resolve_type_hint
from plum.util import TypeHint

__all__ = ["AmbiguousLookupError", "NotFoundLookupError"]


class AmbiguousLookupError(LookupError):
    """A signature cannot be resolved due to ambiguity."""


class NotFoundLookupError(LookupError):
    """A signature cannot be resolved because no applicable method can be found."""


class Resolver:
    """Method resolver.

    Attributes:
        signatures (list[:class:`.signature.Signature`]): Registered signatures.
        is_faithful (bool): Whether all signatures are faithful or not.
    """

    def __init__(self, signatures: Iterable[Signature]):
        signatures_dict = {hash(s): s for s in signatures}
        self.signatures: List[Signature] = list(signatures_dict.values())
        self.is_faithful: bool = all(s.is_faithful for s in self.signatures)
        self._cache = {}

    def __len__(self) -> int:
        return len(self.signatures)

    def clear_cache(self):
        self._cache = {}

    def resolve_method_with_cache(
        self,
        args: Union[Tuple[object, ...], Signature, None] = None,
        types: Optional[Tuple[TypeHint, ...]] = None,
    ) -> Tuple[Callable, TypeHint]:
        if args is None and types is None:
            raise ValueError(
                "Arguments `args` and `types` cannot both be `None`. "
                "This should never happen!"
            )

        if types is None:
            # Attempt to use the cache based on the types of the arguments.
            types = tuple(map(type, args))
        try:
            return self._cache[types]
        except KeyError:
            if args is None:
                args = Signature(*(resolve_type_hint(t) for t in types))

            # Cache miss. Run the resolver based on the arguments.
            method, return_type = self._resolve_method(args)
            # If the resolver is faithful, then we can perform caching using the types
            # of the arguments. If the resolver is not faithful, then we cannot.
            if self.is_faithful:
                self._cache[types] = method, return_type
            return method, return_type

    def _resolve_method(
        self, target: Union[Tuple[object, ...], Signature]
    ) -> Tuple[Callable, TypeHint]:
        """Find the method and return type for arguments.

        Args:
            target (object): Target.

        Returns:
            function: Method.
            type: Return type.
        """
        signature = self._resolve(target)
        return signature.implementation, signature.return_type

    def _resolve(self, target: Union[Tuple[object, ...], Signature]) -> Signature:
        """Find the most specific signature that satisfies a target.

        Args:
            target (:class:`.signature.Signature` or tuple[object]): Target to resolve.
                Must be either a signature to be encompassed or a tuple of arguments.

        Returns:
            :class:`.signature.Signature`: The most specific signature satisfying
                `target`.
        """
        if isinstance(target, tuple):

            def check(s):
                # `target` are concrete arguments.
                return s.match(target)

        else:

            def check(s):
                # `target` is a signature that must be encompassed.
                return target <= s

        candidates = []
        for signature in [s for s in self.signatures if check(s)]:
            # If none of the candidates are comparable, then add the method as
            # a new candidate and continue.
            if not any(c.is_comparable(signature) for c in candidates):
                candidates += [signature]
                continue

            # The signature under consideration is comparable with at least one
            # of the candidates. First, filter any strictly more general candidates.
            new_candidates = [c for c in candidates if not signature < c]

            # If the signature under consideration is as specific as at least
            # one candidate, then and only then add it as a candidate.
            if any(signature <= c for c in candidates):
                candidates = new_candidates + [signature]
            else:
                candidates = new_candidates

        if len(candidates) == 0:
            # There is no matching signature.
            raise NotFoundLookupError(f"`{target}` could not be resolved.")
        elif len(candidates) == 1:
            # There is exactly one matching signature. Success!
            return candidates[0]
        else:
            # There are multiple matching signatures. Before raising an exception,
            # attempt to resolve the ambiguity using the precedence of the signatures.
            precedences = [c.precedence for c in candidates]
            max_precendence = max(precedences)
            if sum([p == max_precendence for p in precedences]) == 1:
                return candidates[precedences.index(max_precendence)]
            else:
                # Could not resolve the ambiguity, so error. First, make a nice list
                # of the candidates and their precedences.
                listed_candidates = "\n  ".join(
                    [f"{c} (precedence: {c.precedence})" for c in candidates]
                )
                raise AmbiguousLookupError(
                    f"`{target}` is ambiguous among the following:\n"
                    f"  {listed_candidates}"
                )
