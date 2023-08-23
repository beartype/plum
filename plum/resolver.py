from typing import List, Tuple, Union

from plum.signature import Signature

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

    def __init__(self):
        self.signatures: List[Signature] = []
        self.is_faithful: bool = True

    def register(self, signature: Signature) -> None:
        """Register a new signature.

        Args:
            signature (:class:`.signature.Signature`): Signature to add.
        """
        existing = [s == signature for s in self.signatures]
        if any(existing):
            if sum(existing) != 1:
                raise AssertionError(
                    f"The added signature `{signature}` is equal to {sum(existing)} "
                    f"existing signatures. This should never happen."
                )
            self.signatures[existing.index(True)] = signature
        else:
            self.signatures.append(signature)

        # Use a double negation for slightly better performance.
        self.is_faithful = not any(not s.is_faithful for s in self.signatures)

    def __len__(self) -> int:
        return len(self.signatures)

    def resolve(self, target: Union[Tuple[object, ...], Signature]) -> Signature:
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
