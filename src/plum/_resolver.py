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
    # Ensure that the implementation has the right name, because this name
    # will show up in the docstring.
    if f_name is not None and getattr(f, "__name__", None) != f_name:
        f = _change_function_name(f, f_name)

    # :class:`pydoc._PlainTextDoc` removes styling. This styling will display
    # erroneously in Sphinx.
    parts = pydoc._PlainTextDoc().document(f).rstrip().split("\n")  # type: ignore[attr-defined]

    # Separate out the function definition and the lines corresponding to the body.
    title = parts[0]
    body = parts[1:]

    # Remove indentation from every line of the body. This indentation defaults to
    # four spaces.
    body = [line[4:] for line in body]

    # If `sphinx` is imported, assume that we're building the documentation. In that
    # case, display the function definition in a nice way.
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
    return any(is_generic_hint(t) for t in m.signature.types) or (
        m.signature.has_varargs and is_generic_hint(m.signature.varargs)
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
    """
    if len(methods) <= 1:
        return list(methods)
    result: list[Method] = []
    remaining = list(methods)
    while remaining:
        # A method is in the current "most specific" layer if no other
        # remaining method is strictly more specific than it.
        layer = [
            m
            for m in remaining
            if not any(
                other is not m and other.signature < m.signature for other in remaining
            )
        ]
        if not layer:  # Safety valve — should never happen with a valid partial order.
            result.extend(remaining)
            break
        result.extend(layer)
        for m in layer:
            remaining.remove(m)
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

        existing = [m.signature == signature for m in self.methods]
        if any(existing):
            if sum(existing) != 1:
                raise AssertionError(
                    f"The added method `{method}` is equal to {sum(existing)} "
                    f"existing methods. This should never happen."
                )

            if self.warn_redefinition:
                # Determine the new and previous implementation. Unwrap possible
                # wrapping by Plum from :meth:`Function.invoke`s, which can obscure the
                # location where the implementation was originally defined.
                previous_method = self.methods[existing.index(True)]
                prev_impl = _unwrap_invoked_methods(previous_method.implementation)
                impl = _unwrap_invoked_methods(method.implementation)
                warnings.warn(
                    f"`{method}` (`{repr_source_path(impl)}`) "
                    f"overwrites the earlier definition "
                    f"`{previous_method}` "
                    f"(`{repr_source_path(prev_impl)}`).",
                    category=MethodRedefinitionWarning,
                    stacklevel=0,
                )

            self.methods[existing.index(True)] = method
        else:
            self.methods.append(method)

        # Use a double negation for slightly better performance.
        self.is_faithful = not any(not s.signature.is_faithful for s in self.methods)

        # True when every method is either faithful OR carries a generic hint in
        # its positional types or varargs (and thus can only be reached via the
        # generic arm, not the bare-type fallback).  When True, caching by bare
        # type on the non-generic arm is safe even if the resolver as a whole is
        # not faithful.
        self.is_faithful_for_non_generic = all(
            m.signature.is_faithful or _method_has_generic_hint(m) for m in self.methods
        )

        # Collect the bare origin types of all parameterised generic hints
        # (e.g. `list` from `list[int]`, `dict` from `dict[str, int]`).
        # Deduplicated (dict.fromkeys preserves first-seen order) so that the
        # `needs_generic` check in _resolve_method_with_cache performs exactly
        # one issubclass call per distinct origin, not one per overload.
        self.generic_origins = tuple(
            dict.fromkeys(
                cast(type, get_origin(t))
                for m in self.methods
                for t in (
                    list(m.signature.types)
                    + ([m.signature.varargs] if m.signature.has_varargs else [])
                )
                if is_generic_hint(t) and isinstance(get_origin(t), type)
            )
        )
        self.has_generic_signatures = bool(self.generic_origins)

        # Pre-compute per-origin sorted method lists for arity-1 fast dispatch.
        # Only populated when every registered method is single-argument with no
        # varargs, so multi-arity functions fall back to the regular resolver.
        if self.has_generic_signatures and all(
            len(m.signature.types) == 1 and not m.signature.has_varargs
            for m in self.methods
        ):
            self._arity1_methods = {
                origin: _sort_most_specific_first(
                    [
                        m
                        for m in self.methods
                        if m.signature.types
                        and _can_match_arity1_origin(m.signature.types[0], origin)
                    ]
                )
                for origin in set(self.generic_origins)
            }
        else:
            self._arity1_methods = {}

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
        for method in [m for m in methods if check(m)]:
            # If none of the candidates are comparable, then add the method as
            # a new candidate and continue.
            if not any(c.signature.is_comparable(method.signature) for c in candidates):
                candidates += [method]
                continue

            # The signature under consideration is comparable with at least one
            # of the candidates. First, filter any strictly more general candidates.
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
            # There are multiple matching signatures. Before raising an exception,
            # attempt to resolve the ambiguity using the precedence of the signatures.
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

        # Gather methods from all registered origins that arg_type is a subtype of,
        # deduplicating across overlapping origin buckets (e.g. list & Sequence).
        seen: set[int] = set()
        relevant: list[Method] = []
        for origin, methods in self._arity1_methods.items():
            if issubclass(bare_type, origin):
                for m in methods:
                    mid = id(m)
                    if mid not in seen:
                        seen.add(mid)
                        relevant.append(m)

        if not relevant:
            return self.resolve(target)

        if len(relevant) > 1:
            relevant = _sort_most_specific_first(relevant)
        return self._resolve_from(target, relevant)
