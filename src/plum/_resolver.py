__all__ = ("AmbiguousLookupError", "NotFoundLookupError")

import pydoc
import sys
import warnings
from collections.abc import Callable, Iterable
from functools import wraps
from typing import cast, get_origin

from rich.console import Console, ConsoleOptions
from rich.padding import Padding
from rich.text import Text

from ._generic import is_generic_hint
from ._util import argsort
from plum._method import Method, MethodList
from plum._signature import Signature
from plum.repr import repr_source_path, rich_repr


class MethodRedefinitionWarning(Warning):
    """A method is redefined."""


def _render_function_call(f: str, target: tuple[object, ...] | Signature, /) -> str:
    """Render a function call.

    Args:
        f (str): Function name
        target (tuple or :class:`.Signature`): Arguments or signature.

    Returns:
        str: Rendered call.
    """
    if isinstance(target, tuple):
        target_rendered = "(" + ", ".join(repr(arg) for arg in target) + ")"
    else:
        target_rendered = str(target)
        # Remove the prefix `Signature`.
        target_rendered = target_rendered[len("Signature") :]
    return f"{f}{target_rendered}"


@rich_repr(str=True)
class AmbiguousLookupError(LookupError):
    """A signature cannot be resolved due to ambiguity."""

    def __init__(
        self,
        f_name: str | None,
        target: tuple[object, ...] | Signature,
        methods: MethodList,
    ):
        """Create a new :class:`AmbiguousLookupError`.

        Args:
            f_name (str or :obj:`None`): Name (or qualified name) of the function that
                could not be resolved.
            target (Union[Tuple, :class:`.Signature`]): Target signature or arguments
                that could not be resolved.
            methods (:class:`.MethodList`): List of ambiguous methods.
        """
        self.f_name = f_name if f_name is not None else "<function>"
        self.target = target
        self.methods = methods

    def __rich_console__(
        self, console: Console, options: ConsoleOptions, /
    ) -> Iterable[Text | Padding]:
        yield Text(f"`{_render_function_call(self.f_name, self.target)}` is ambiguous.")
        yield Text()
        yield Text("Candidates:")
        for m in self.methods:
            yield Padding(m.repr_mismatch(), (0, 3))


@rich_repr(str=True)
class NotFoundLookupError(LookupError):
    """A signature cannot be resolved because no applicable method can be found.

    This error object is used to display the closest methods to the target signature.
    """

    def __init__(
        self,
        f_name: str | None,
        target: tuple[object, ...] | Signature,
        methods: MethodList,
        *,
        max_suggestions: int = 3,
    ):
        """Create a new :class:`NotFoundLookupError`.

        Args:
            f_name (str or :obj:`None`): Name (or qualified name) of the function that
                could not be resolved.
            target (Union[Tuple, :class:`Signature`]): Target signature or arguments
                that could not be resolved.
            methods (:class:`MethodList`): Methods that were considered.
            max_suggestions (int, optional): Maximum number of displayed signatures.
                Defaults to three.
        """
        self.f_name = f_name if f_name is not None else "<function>"
        self.target = target
        self.methods = methods

        self.max_suggestions = max_suggestions

    def __rich_console__(
        self, console: Console, options: ConsoleOptions, /
    ) -> Iterable[Text | Padding]:
        """Generate a string of the top `self.max_suggestions` methods that are closest
        to the given one."""
        yield Text(
            f"`{_render_function_call(self.f_name, self.target)}` "
            f"could not be resolved."
        )

        if not isinstance(self.target, Signature):
            distances = []
            for method in self.methods:
                dist = method.signature.compute_distance(self.target)
                distances.append(dist)

            sort_method_ids = argsort(distances)

            # Take at most `self.max_suggestions` hints.
            sort_method_ids = sort_method_ids[: self.max_suggestions]

            distances = [distances[i] for i in sort_method_ids]
            methods = [self.methods[i] for i in sort_method_ids]

            # Create the list of candidates.
            yield Text()
            yield Text("Closest candidates are the following:")
            for m in methods:
                misses, varargs_matched = m.signature.compute_mismatches(self.target)
                yield Padding(
                    m.repr_mismatch(frozenset(misses), varargs_matched), (0, 4)
                )


def _change_function_name(
    f: Callable[..., object], name: str, /
) -> Callable[..., object]:
    """It is not always the case that `f.__name__` is writable. To solve this, first
    create a temporary function that wraps `f` and then change the name.

    Args:
        f (function): Function to change the name of.
        name (str): New name.

    Returns:
        function: Function that wraps `f` and has name `name`.
    """

    @wraps(f)
    def f_renamed(*args: object, **kw_args: object) -> object:
        return f(*args, **kw_args)  # pragma: no cover

    f_renamed.__name__ = name
    return f_renamed


def _document(f: Callable[..., object], f_name: str | None = None, /) -> str:
    """Generate documentation for a function `f`.

    The generated documentation contains both the function definition and the
    docstring. The docstring is on the same level of indentation of the function
    definition. There will be no trailing newlines.

    If the package :mod:`sphinx` is not imported, then the function definition will
    be preceded by the string `<separator>`.

    If the package :mod:`sphinx` is imported, then the function definition will include
    a Sphinx directive to displays the function definition in a nice way.

    Args:
        f (function): Function.
        f_name (str): An optional string representing the function name, which will be
            overridden from implementation's docstring which might have a different
            name. If this is not specified, the name is not overriden.

    Returns:
        str: Documentation for `f`.
    """
    # Ensure that the implementation has the right name, because this name will
    # show up in the docstring.
    if f_name is not None and getattr(f, "__name__", None) != f_name:
        f = _change_function_name(f, f_name)

    # :class:`pydoc._PlainTextDoc` removes styling. This styling will display
    # erroneously in Sphinx.
    parts = pydoc._PlainTextDoc().document(f).rstrip().split("\n")  # type: ignore[attr-defined]

    # Separate out the function definition and the lines corresponding to the
    # body.
    title = parts[0]
    body = parts[1:]

    # Remove indentation from every line of the body. This indentation defaults
    # to four spaces.
    body = [line[4:] for line in body]

    # If `sphinx` is imported, assume that we're building the documentation. In
    # that case, display the function definition in a nice way.
    if "sphinx" in sys.modules:
        title = ".. py:function:: " + title + "\n   :noindex:"
    else:
        title = "<separator>\n\n" + title
    title += "\n"  # Add a newline to separate the title from the body.

    # Ensure that there are no trailing newlines. This can happen if the body is empty.
    return "\n".join([title] + body).rstrip()


def _unwrap_invoked_methods(f: Callable[..., object], /) -> Callable[..., object]:
    """Undo wrapping of :meth:`Function.invoke`d methods.

    :meth:`Function.invoke` uses :func:`functools.wraps` to wrap the function and
    convert the output to the right return type. This wrapping obscures where the
    method was originally defined, meaning that :func:`plum.repr.repr_source_path`
    gives erroneous results. This function undoes that wrapping and makes
    :func:`plum.repr.repr_source_path` work correctly.

    Args:
        f (function): Function, possibly wrapped.

    Returns:
        function: `f`, but without any wrapping.
    """
    while hasattr(f, "__wrapped_by_plum__"):
        f = f.__wrapped_by_plum__
    return f


def _method_has_generic_hint(m: "Method") -> bool:
    """Return True if *m* has a generic hint in its positional types or varargs.

    Used to classify methods as reachable only via the generic arm so that
    bare-type caching on the non-generic arm remains safe.
    """
    sig = m.signature
    return any(is_generic_hint(t) for t in sig.types) or (
        sig.has_varargs and is_generic_hint(sig.varargs)
    )


def _can_match_arity1_origin(hint: object, origin: type) -> bool:
    """True if an arg of bare type `origin` could possibly match `hint`.

    Used to pre-filter the method list for the arity-1 fast dispatch path.
    """
    if is_generic_hint(hint):
        hint_origin = get_origin(hint)
        return isinstance(hint_origin, type) and issubclass(origin, hint_origin)
    elif isinstance(hint, type):
        return issubclass(origin, hint)
    return False


def _sort_most_specific_first(methods: list["Method"]) -> list["Method"]:
    """Topological sort: most-specific methods first.

    Uses the Signature partial order: ``m1 < m2`` means m1 is strictly more
    specific than m2.  Methods that are incomparable remain in their relative
    order within the same topological layer.

    Implements Kahn's algorithm on the "more-specific-than" DAG.  Each
    unordered pair is checked with exactly two ``__le__`` calls; the strict
    relation follows as ``le_ij and not le_ji``.  This avoids the
    ``Signature.__eq__`` calls that ``Comparable.__lt__`` incurs (once per
    True comparison) and that ``list.remove()`` incurs (once per non-matching
    element scan), both of which require ``TypeHintWrapper`` construction.
    """
    n = len(methods)
    if n <= 1:
        return list(methods)

    # Pre-compute the partial order in one pass over unordered pairs.
    # in_degree[i]   = number of methods strictly more specific than methods[i]
    # successors[i]  = indices of methods that methods[i] is strictly more
    #                  specific than (i.e. the nodes i "dominates")
    in_degree = [0] * n
    successors: list[list[int]] = [[] for _ in range(n)]

    for i in range(n):
        sig_i = methods[i].signature
        for j in range(i + 1, n):
            le_ij = sig_i <= methods[j].signature
            le_ji = methods[j].signature <= sig_i
            if le_ij and not le_ji:  # i strictly more specific than j
                in_degree[j] += 1
                successors[i].append(j)
            elif le_ji and not le_ij:  # j strictly more specific than i
                in_degree[i] += 1
                successors[j].append(i)
            # else: equal or incomparable — no edge

    # Kahn's BFS: process in stable original-index order within each layer.
    # The initial queue is in index order (the comprehension preserves it), and
    # each successive layer is re-sorted by original index.  Without that sort,
    # a layer's nodes would come out in discovery order (which predecessor
    # freed them last), reordering incomparable methods within the layer.
    result: list[Method] = []
    queue = [i for i, d in enumerate(in_degree) if not d]
    while queue:
        result.extend(methods[i] for i in queue)
        next_queue: list[int] = []
        for i in queue:
            for j in successors[i]:
                in_degree[j] -= 1
                if in_degree[j] == 0:
                    next_queue.append(j)
        next_queue.sort()
        queue = next_queue

    if len(result) < n:
        # Safety valve — should never happen with a valid partial order.  A
        # cyclic __le__ relation leaves some nodes with in_degree > 0.
        seen = {id(m) for m in result}
        result.extend(m for m in methods if id(m) not in seen)

    return result


class Resolver:
    """Method resolver.

    Args:
        function_name (str, optional): Name of the function.
        warn_redefinition (bool, optional): Throw a warning whenever a method is
            redefined. Defaults to `False`.

    Attributes:
        methods (list[:class:`.method.Method`]): Registered methods.
        is_faithful (bool): Whether all methods are faithful or not.
        warn_redefinition (bool): Throw a warning whenever a method is redefined.
    """

    __slots__ = (
        "function_name",
        "methods",
        "is_faithful",
        "is_faithful_for_non_generic",
        "has_generic_signatures",
        "generic_origins",
        "_arity1_methods",
        "warn_redefinition",
    )

    def __init__(
        self,
        function_name: str | None = None,
        warn_redefinition: bool = False,
    ) -> None:
        """Initialise the resolver.

        Args:
            function_name (str, optional): Name of the function.
        """
        self.function_name = function_name
        self.methods: MethodList = MethodList()
        self.is_faithful: bool = True
        self.is_faithful_for_non_generic: bool = True
        self.has_generic_signatures: bool = False
        self.generic_origins: tuple[type, ...] = ()
        self._arity1_methods: dict[type, list[Method]] = {}
        self.warn_redefinition = warn_redefinition

    def doc(self, exclude: Callable[..., object] | None = None) -> str:
        """Concatenate the docstrings of all methods of this function. Remove duplicate
        docstrings before concatenating.

        Args:
            exclude (function, optional): Exclude this implementation from the
                concatenation.

        Returns:
            str: Concatenation of all docstrings.
        """
        # Generate all docstrings, possibly excluding `exclude`.
        docs = [
            _document(m.implementation, self.function_name)
            for m in self.methods
            if not (exclude and m.implementation == exclude)
        ]
        # This can yield duplicates, because of extra methods automatically generated by
        # :func:`.signature.append_default_args`. We remove these by simply only
        # keeping unique docstrings.
        unique_docs = []
        for d in docs:
            if d not in unique_docs:
                unique_docs.append(d)
        # The unique documentations have no trailing newlines, so separate them with
        # a newline.
        return "\n\n".join(unique_docs)

    def register(self, method: Method) -> None:
        """Register a new method.

        Args:
            method (:class:`.method.Method`): Method to add.
        """
        signature = method.signature

        # Exhaustively scan for existing methods with an equal signature.
        # register() is not a hot path, and it is more important to detect a
        # broken "at most one equal signature" invariant than to stop at the
        # first match.
        _equal_indices = [
            i for i, m in enumerate(self.methods) if m.signature == signature
        ]
        if len(_equal_indices) > 1:
            raise AssertionError(
                f"The added method `{method}` is equal to {len(_equal_indices)} "
                f"existing methods. This should never happen."
            )
        existing_idx = _equal_indices[0] if _equal_indices else None
        if existing_idx is not None:
            # Save the replaced method before overwriting: needed below to swap
            # the reference inside _arity1_methods buckets.
            _replaced_method = self.methods[existing_idx]
            if self.warn_redefinition:
                # Determine the new and previous implementation. Unwrap possible
                # wrapping by Plum from :meth:`Function.invoke`s, which can obscure the
                # location where the implementation was originally defined.
                prev_impl = _unwrap_invoked_methods(_replaced_method.implementation)
                impl = _unwrap_invoked_methods(method.implementation)
                warnings.warn(
                    f"`{method}` (`{repr_source_path(impl)}`) "
                    f"overwrites the earlier definition "
                    f"`{_replaced_method}` "
                    f"(`{repr_source_path(prev_impl)}`).",
                    category=MethodRedefinitionWarning,
                    stacklevel=0,
                )

            self.methods[existing_idx] = method
        else:
            _replaced_method = None
            self.methods.append(method)

        # --- is_faithful ---
        # REPLACE: same signature ⇒ same types ⇒ faithfulness is unchanged.
        # APPEND: if already False it stays False; otherwise check only the new method.
        if existing_idx is None and self.is_faithful:
            self.is_faithful = signature.is_faithful

        # True when every method is either faithful OR carries a generic hint in
        # its positional types or varargs (and thus can only be reached via the
        # generic arm, not the bare-type fallback).  When True, caching by bare
        # type on the non-generic arm is safe even if the resolver as a whole is
        # not faithful.
        #
        # Updated incrementally: only call _method_has_generic_hint for the
        # new/replacement method rather than rescanning all methods each time.
        _new_ok = signature.is_faithful or _method_has_generic_hint(method)
        if existing_idx is None:
            # Appending: conjoin with the existing flag.
            self.is_faithful_for_non_generic = (
                self.is_faithful_for_non_generic and _new_ok
            )
        elif not self.is_faithful_for_non_generic and _new_ok:
            # Replacing when the flag is currently False but the replacement
            # conforms: the replaced method may have been the sole violator, so
            # a full rescan is needed to determine whether the flag becomes True.
            self.is_faithful_for_non_generic = all(
                m.signature.is_faithful or _method_has_generic_hint(m)
                for m in self.methods
            )
        else:
            # Replacing when the flag is True (only the new method determines
            # the outcome) or when the new method also fails (stays False).
            self.is_faithful_for_non_generic = _new_ok

        # --- generic_origins and has_generic_signatures ---
        # REPLACE: same signature ⇒ same types ⇒ generic_origins is unchanged.
        # APPEND: scan only the new method's types rather than all methods.
        if existing_idx is None:
            _was_generic_before = self.has_generic_signatures
            _new_method_types = signature.types + (
                (signature.varargs,) if signature.has_varargs else ()
            )
            _new_origins = tuple(
                dict.fromkeys(
                    cast(type, get_origin(t))
                    for t in _new_method_types
                    if is_generic_hint(t) and isinstance(get_origin(t), type)
                )
            )
            if _new_origins:
                _existing_set = set(self.generic_origins)
                _fresh = tuple(o for o in _new_origins if o not in _existing_set)
                if _fresh:
                    self.generic_origins = self.generic_origins + _fresh
            self.has_generic_signatures = bool(self.generic_origins)

        # --- _arity1_methods ---
        # The dict is valid iff has_generic_signatures AND every registered method
        # is single-argument (no varargs).
        if existing_idx is not None:
            # REPLACE: same signature ⇒ same arity ⇒ fast-path eligibility
            # unchanged.  Only swap the old method reference with the new one in
            # each bucket.
            if self._arity1_methods:
                for _bucket in self._arity1_methods.values():
                    for _i, _m in enumerate(_bucket):
                        if _m is _replaced_method:
                            _bucket[_i] = method
                            break
        else:
            # APPEND: check whether the arity-1 fast path is still applicable.
            _new_is_arity1 = len(signature.types) == 1 and not signature.has_varargs
            if not self.has_generic_signatures or not _new_is_arity1:
                # Either no generic signatures, or new method is not arity-1.
                self._arity1_methods = {}
            elif self._arity1_methods:
                # Was already populated ⇒ all previous methods are arity-1.
                # Add the new method to the relevant origin buckets incrementally.
                for _origin in set(self.generic_origins):
                    if _can_match_arity1_origin(signature.types[0], _origin):
                        self._arity1_methods[_origin] = _sort_most_specific_first(
                            self._arity1_methods.get(_origin, []) + [method]
                        )
            elif not _was_generic_before and all(
                # First generic method added; _arity1_methods was empty because
                # all previous methods were non-generic (not because one was
                # non-arity-1).  Do a one-time full build if all methods are
                # arity-1.
                len((s := m.signature).types) == 1 and not s.has_varargs
                for m in self.methods
            ):
                self._arity1_methods = {
                    _origin: _sort_most_specific_first(
                        [
                            m
                            for m in self.methods
                            if (ts := m.signature.types)
                            and _can_match_arity1_origin(ts[0], _origin)
                        ]
                    )
                    for _origin in set(self.generic_origins)
                }
            # else: _was_generic_before=True, _arity1_methods={}: some prior
            # method was not arity-1, so the fast path stays disabled.

    def __len__(self) -> int:
        return len(self.methods)

    def resolve(self, target: tuple[object, ...] | Signature) -> Method:
        """Find the most specific signature that satisfies a target.

        Args:
            target (:class:`.signature.Signature` or tuple[object]): Target to resolve.
                Must be either a signature to be encompassed or a tuple of arguments.

        Returns:
            :class:`.signature.Signature`: The most specific signature satisfying
                `target`.
        """
        return self._resolve_from(target, self.methods)

    def _resolve_from(
        self,
        target: tuple[object, ...] | Signature,
        methods: "MethodList | list[Method]",
    ) -> Method:
        """Core resolution algorithm operating on the given methods list."""
        if isinstance(target, tuple):

            def check(m: Method, /) -> bool:
                # `target` are concrete arguments.
                return bool(m.signature.match(target))

        else:

            def check(m: Method, /) -> bool:
                # `target` is a signature that must be encompassed.
                return bool(target <= m.signature)

        candidates: list[Method] = []
        for method in methods:
            if not check(method):
                continue
            # If none of the candidates are comparable, then add the method as
            # a new candidate and continue.
            if not any(c.signature.is_comparable(method.signature) for c in candidates):
                candidates += [method]
                continue

            # The signature under consideration is comparable with at least one
            # of the candidates. First, filter any strictly more general
            # candidates.
            new_candidates = [
                c for c in candidates if not method.signature < c.signature
            ]

            # If the signature under consideration is as specific as at least
            # one candidate, then and only then add it as a candidate.
            if any(method.signature <= c.signature for c in candidates):
                candidates = new_candidates + [method]
            else:
                candidates = new_candidates

        if len(candidates) == 0:
            # There is no matching signature.
            raise NotFoundLookupError(self.function_name, target, self.methods)

        elif len(candidates) == 1:
            # There is exactly one matching signature. Success!
            return candidates[0]
        else:
            # There are multiple matching signatures. Before raising an
            # exception, attempt to resolve the ambiguity using the precedence
            # of the signatures.
            precedences = [c.signature.precedence for c in candidates]
            max_precendence = max(precedences)
            if sum([p == max_precendence for p in precedences]) == 1:
                return candidates[precedences.index(max_precendence)]
            else:
                # Could not resolve the ambiguity, so error.
                raise AmbiguousLookupError(
                    self.function_name, target, MethodList(candidates)
                )

    def resolve_for_type(self, target: tuple[object, ...], arg_type: object) -> Method:
        """Arity-1 cold-miss shortcut using the pre-filtered ``_arity1_methods`` map.

        Gathers only the methods that could match an arg of ``arg_type``, avoiding
        a full scan of all registered methods.  Falls back to :meth:`resolve` when
        ``_arity1_methods`` is empty (non-arity-1 or non-generic function).

        Args:
            target: Concrete single-element argument tuple.
            arg_type: ``type(target[0])`` for plain values, or
                ``target[0].__orig_class__`` (a subscripted generic alias such as
                ``Box[int]``) for instances constructed via ``Box[int](...)``.

        Returns:
            :class:`.method.Method`: Best matching method.
        """
        if not self._arity1_methods:
            return self.resolve(target)

        # ``arg_type`` may be a subscripted generic alias (e.g. ``Box[int]``)
        # when the caller was constructed via ``Box[int](...)``.  The
        # ``_arity1_methods`` dict is keyed by bare origin types, so we need the
        # origin for the ``issubclass`` check.
        bare_type: type
        arg_origin = get_origin(arg_type)
        if arg_origin is not None:
            bare_type = arg_origin
        elif isinstance(arg_type, type):
            bare_type = arg_type
        else:
            # Unexpected; fall back to full resolution.
            return self.resolve(target)

        # Gather methods from all registered origins that arg_type is a subtype
        # of, deduplicating across overlapping origin buckets (e.g. list &
        # Sequence).
        seen: set[int] = set()
        relevant: list[Method] = [
            m
            for methods in (
                v for k, v in self._arity1_methods.items() if issubclass(bare_type, k)
            )
            for m in methods
            if not (id(m) in seen or seen.add(id(m)))  # type: ignore[func-returns-value]
        ]

        if not relevant:
            return self.resolve(target)

        if len(relevant) > 1:
            relevant = _sort_most_specific_first(relevant)
        try:
            return self._resolve_from(target, relevant)
        except NotFoundLookupError:
            # The prefiltered bucket may omit matching fallback methods whose
            # annotations are not generic hints and not plain types (e.g.
            # ``typing.Any``, ``Union[list, dict]``).  Such hints are excluded
            # from every origin bucket, so the filtered list can miss a valid
            # match.  Fall back to full resolution over all registered methods.
            return self.resolve(target)
