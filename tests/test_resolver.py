import inspect
import sys
import textwrap
import warnings
from unittest.mock import patch

import pytest

from tests.util import rich_render

import plum
from plum._resolver import (
    MethodRedefinitionWarning,
    Resolver,
    _document,
    _render_function_call,
    _sort_most_specific_first,
)


def test_render_function_call():
    assert _render_function_call("f", (1,)) == "f(1)"
    assert _render_function_call("f", (1, 1)) == "f(1, 1)"
    assert _render_function_call("f", plum.Signature(int)) == "f(int)"
    assert _render_function_call("f", plum.Signature(int, int)) == "f(int, int)"


def test_initialisation():
    r = Resolver()
    # Without any registered signatures, the resolver should be faithful.
    assert r.is_faithful


def test_document_nosphinx():
    """Test the following:
    (1) remove trailing newlines,
    (2) appropriately remove trailing newlines,
    (3) appropriately remove indentation, ignoring the first line,
    (4) separate the title from the body.
    """

    def f(x):
        """Title.

        Hello.

        Args:
            x (object): Input.

        """

    expected_doc = """
    <separator>

    f(x)

    Title.

    Hello.

    Args:
        x (object): Input.
    """
    assert _document(f, "f") == textwrap.dedent(expected_doc).strip()


def test_document_sphinx(monkeypatch):
    """Like :func:`test_document_nosphinx`, but when :mod:`sphinx`
    is imported."""
    # Fake import :mod:`sphinx`.
    monkeypatch.setitem(sys.modules, "sphinx", None)

    def f(x):
        """Title.

        Hello.

        Args:
            x (object): Input.

        """

    expected_doc = """
    .. py:function:: f(x)
       :noindex:

    Title.

    Hello.

    Args:
        x (object): Input.
    """
    assert _document(f, "f") == textwrap.dedent(expected_doc).strip()


@pytest.mark.incompatible_with_mypyc
def test_doc(monkeypatch):
    # Let the `pydoc` documenter simply return the docstring. This makes testing
    # simpler.
    monkeypatch.setattr(plum._resolver, "_document", lambda x, _: x.__doc__)

    r = Resolver()

    class _MockFunction:
        def __init__(self, doc):
            self.__doc__ = doc

    class _MockMethod:
        def __init__(self, doc):
            self.implementation = _MockFunction(doc)

    # Circumvent the use of :meth:`.resolver.Resolver.register`.
    r.methods = [
        _MockMethod("first"),
        _MockMethod("second"),
        _MockMethod("third"),
    ]
    assert r.doc() == "first\n\nsecond\n\nthird"

    # Test that duplicates are excluded.
    r.methods = [
        _MockMethod("first"),
        _MockMethod("second"),
        _MockMethod("second"),
        _MockMethod("third"),
    ]
    assert r.doc() == "first\n\nsecond\n\nthird"

    # Test that the explicit exclusion mechanism also works.
    assert r.doc(exclude=r.methods[3].implementation) == "first\n\nsecond"


def test_register():
    r = Resolver()

    def f(*xs):
        return xs

    # Test that faithfulness is tracked correctly.
    r.register(plum.Method(f, plum.Signature(int)))
    r.register(plum.Method(f, plum.Signature(float)))
    assert r.is_faithful
    r.register(plum.Method(f, plum.Signature(tuple[int])))
    assert not r.is_faithful

    # Test that signatures can be replaced.
    new_m = plum.Method(f, plum.Signature(float))
    assert len(r) == 3
    assert r.methods[1] is not new_m
    r.register(new_m)
    assert len(r) == 3
    assert r.methods[1] is new_m


def test_register_short_circuits_on_first_match():
    """``register`` must stop scanning after the first matching signature.

    ``register`` uses ``next()`` with a generator expression so that scanning
    stops as soon as the first matching signature is found.

    Scenario: resolver with 2 methods (``int`` at index 0, ``float`` at
    index 1).  Re-registering ``int`` should require exactly one
    ``Signature.__eq__`` call (int==int → True → stop).
    """

    def f(*xs):
        return xs

    r = Resolver()
    r.register(plum.Method(f, plum.Signature(int)))  # index 0
    r.register(plum.Method(f, plum.Signature(float)))  # index 1

    eq_calls = 0
    real_eq = plum.Signature.__eq__

    def counting_eq(self, other):
        nonlocal eq_calls
        eq_calls += 1
        return real_eq(self, other)

    # Re-register the FIRST method.  next() stops after int==int = 1 call.
    with patch.object(plum.Signature, "__eq__", counting_eq):
        r.register(plum.Method(f, plum.Signature(int)))

    assert len(r) == 2, "Redefinition must not change the method count"
    assert (
        eq_calls == 1
    ), f"Expected 1 Signature.__eq__ call (early break on match), got {eq_calls}"


def test_register_metadata_updated_incrementally():
    """``register`` must update ``generic_origins`` and ``_arity1_methods``
    incrementally rather than rescanning all registered methods on every call.

    The test uses arity-1 methods whose sole type is ``list[X]`` (a parameterised
    generic) so that:

    - ``is_faithful`` is ``False`` for every signature;
    - ``_method_has_generic_hint`` returns ``True``, qualifying methods for the
      arity-1 fast path;
    - ``generic_origins = (list,)`` after the first registration;
    - ``_arity1_methods`` is populated on every subsequent registration.

    We count calls to ``is_generic_hint``, which is invoked by three parts of
    the ``register`` implementation — each incremental:

    1. **``_method_has_generic_hint``** — called once per registration for the
       new method only: **1 call**.
    2. **``generic_origins`` computation** — scans only the new method's types:
       **1 call**.
    3. **``_arity1_methods`` update** — checks only the new method's origin:
       **1 call**.

    Expected total for N=4 registrations: **12 calls** (3 per registration).

    The module is loaded from the ``.py`` source so that ``is_generic_hint`` (a
    module-level name in ``_resolver.py``) can be patched via the module dict.
    mypyc-compiled callers use a direct C pointer and bypass the dict lookup.
    """
    import importlib.util
    import pathlib
    import sys as _sys

    # Load _resolver.py from source to get an interpreted Resolver.
    src_path = pathlib.Path(__file__).parent.parent / "src" / "plum" / "_resolver.py"
    _MOD_NAME = "plum._resolver_source"
    spec = importlib.util.spec_from_file_location(_MOD_NAME, str(src_path))
    mod = importlib.util.module_from_spec(spec)
    # Must set __package__ so that the relative imports inside _resolver.py
    # (e.g. ``from ._generic import …``) resolve against the already-loaded
    # compiled ``plum.*`` modules in sys.modules.
    mod.__package__ = "plum"
    _sys.modules[_MOD_NAME] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        _sys.modules.pop(_MOD_NAME, None)

    real_is_generic_hint = mod.is_generic_hint
    call_count = 0

    def counting_is_generic_hint(t):
        nonlocal call_count
        call_count += 1
        return real_is_generic_hint(t)

    def f(*xs):
        return xs

    n_methods = 4
    with patch.object(mod, "is_generic_hint", counting_is_generic_hint):
        r = mod.Resolver()
        for t in (int, float, str, bytes):
            r.register(plum.Method(f, plum.Signature(list[t])))

    # 3 per registration × 4 = 12.
    expected = n_methods * 3
    assert call_count == expected, (
        f"Expected {expected} is_generic_hint calls (3 per registration), "
        f"got {call_count}."
    )


def test_sort_most_specific_first_no_eq_calls():
    """Kahn's algorithm uses only ``__le__``; ``Signature.__eq__`` is never called.

    Kahn's algorithm determines strict ordering via two ``__le__`` calls per
    pair (``le_ij`` and ``le_ji``), deriving ``i < j`` as ``le_ij and not
    le_ji``.  ``Signature.__eq__`` is therefore never called.
    """

    class A:
        pass

    class B(A):
        pass

    class C(B):
        pass

    class D(C):
        pass

    def f(*xs):
        return xs

    # 4-method linear chain registered in least-specific-first order.
    m_A = plum.Method(f, plum.Signature(A))
    m_B = plum.Method(f, plum.Signature(B))
    m_C = plum.Method(f, plum.Signature(C))
    m_D = plum.Method(f, plum.Signature(D))

    real_eq = plum.Signature.__eq__
    eq_call_count = 0

    def counting_eq(self, other, /):
        nonlocal eq_call_count
        eq_call_count += 1
        return real_eq(self, other)

    with patch.object(plum.Signature, "__eq__", counting_eq):
        result = _sort_most_specific_first([m_A, m_B, m_C, m_D])

    assert result[0] is m_D, f"Expected m_D first (most specific), got {result[0]}"
    assert result[-1] is m_A, f"Expected m_A last (least specific), got {result[-1]}"
    assert eq_call_count == 0, (
        f"Expected 0 Signature.__eq__ calls (Kahn's uses __le__ only), "
        f"got {eq_call_count}."
    )


def test_sort_most_specific_first_safety_valve():
    """The safety valve fires when all nodes have in-degree > 0 (cyclic ``__le__``).

    Kahn's algorithm uses ``__le__`` to derive the strict partial order.
    A cyclic ``__le__`` relation leaves every node with in_degree > 0, so the
    BFS queue empties before all methods are emitted; the safety valve then
    appends the remaining methods in their original order.

    This path is unreachable with a valid partial order but we exercise it by
    patching ``Signature.__le__`` to create a three-node cycle:
    m1 → m2 → m3 → m1 (each method "more specific than" the next).
    """

    def f(*xs):
        return xs

    m1 = plum.Method(f, plum.Signature(int))
    m2 = plum.Method(f, plum.Signature(float))
    m3 = plum.Method(f, plum.Signature(str))

    methods = [m1, m2, m3]

    # Directed cycle via __le__:
    #   sig1 ≤ sig2 (not sig2 ≤ sig1)  →  m1 more specific than m2
    #   sig2 ≤ sig3 (not sig3 ≤ sig2)  →  m2 more specific than m3
    #   sig3 ≤ sig1 (not sig1 ≤ sig3)  →  m3 more specific than m1
    # All in-degrees become 1; Kahn's queue starts empty → safety valve fires.
    _le_table = {
        (id(m1.signature), id(m2.signature)): True,
        (id(m2.signature), id(m1.signature)): False,
        (id(m2.signature), id(m3.signature)): True,
        (id(m3.signature), id(m2.signature)): False,
        (id(m3.signature), id(m1.signature)): True,
        (id(m1.signature), id(m3.signature)): False,
    }

    def _cyclic_le(self, other):
        return _le_table.get((id(self), id(other)), False)

    with patch.object(plum.Signature, "__le__", _cyclic_le):
        result = _sort_most_specific_first(methods)

    # Safety valve: all unprocessed methods are appended in original order.
    assert set(result) == {m1, m2, m3}


def test_register_replace_faithful_triggers_rescan():
    """When a faithful method replaces an existing one while
    ``is_faithful_for_non_generic`` is False (due to a *different* unfaithful
    non-generic method), the full-rescan branch (lines 420-423) executes."""

    class _Unfaithful:
        """A plain class that opts out of faithful type-checking."""

        __faithful__ = False

    def f(*xs):
        return xs

    def g(*xs):
        return xs

    r = Resolver()
    # Register an unfaithful, non-generic method → flag becomes False.
    r.register(plum.Method(f, plum.Signature(_Unfaithful)))
    assert not r.is_faithful_for_non_generic

    # Register a faithful method (different signature).
    r.register(plum.Method(f, plum.Signature(int)))
    assert not r.is_faithful_for_non_generic  # still False

    # Replace the faithful ``int`` method with a new implementation.
    # ``_new_ok`` is True (int is faithful); flag is still False → rescan.
    r.register(plum.Method(g, plum.Signature(int)))
    # After rescan the _Unfaithful method is still present, so the flag
    # remains False — but the rescan branch was exercised.
    assert not r.is_faithful_for_non_generic
    # Replacing did not add a new method.
    assert len(r) == 2


def test_register_replace_swaps_arity1_bucket():
    """When an existing method is replaced and ``_arity1_methods`` is already
    populated, the old method reference is swapped for the new one in each
    origin bucket (lines 461-462)."""

    def f(*xs):
        return xs

    def g(*xs):
        return xs

    r = Resolver()
    m1 = plum.Method(f, plum.Signature(list[int]))
    r.register(m1)

    # After the first generic arity-1 registration, _arity1_methods is built.
    assert r._arity1_methods
    assert list in r._arity1_methods
    assert r._arity1_methods[list][0] is m1

    # Replace with a different implementation but identical signature.
    m2 = plum.Method(g, plum.Signature(list[int]))
    r.register(m2)

    # Still one method (replacement, not an addition).
    assert len(r) == 1
    # Bucket now holds m2, not m1.
    assert r._arity1_methods[list][0] is m2


def test_len():
    def f(x):
        return x

    r = Resolver()
    assert len(r) == 0
    r.register(plum.Method(f, plum.Signature(int)))
    assert len(r) == 1
    r.register(plum.Method(f, plum.Signature(float)))
    assert len(r) == 2
    r.register(plum.Method(f, plum.Signature(float)))
    assert len(r) == 2


def test_resolve():
    class A:
        pass

    class B1(A):
        pass

    class B2(A):
        pass

    class C1(B1, B2):
        pass

    class C2(B2):
        pass

    class Unrelated:
        pass

    class Missing:
        pass

    def f(x):
        return x

    m_a = plum.Method(f, plum.Signature(A))
    m_b1 = plum.Method(f, plum.Signature(B1))
    m_b2 = plum.Method(f, plum.Signature(B2))
    m_c1 = plum.Method(f, plum.Signature(C1))
    m_c2 = plum.Method(f, plum.Signature(C2))
    m_u = plum.Method(f, plum.Signature(Unrelated))
    m_m = plum.Method(f, plum.Signature(Missing))

    r = Resolver()
    r.register(m_b1)
    # Import this after `m_b1` to test all branches.
    r.register(m_a)
    r.register(m_b2)
    # Do not register `m_c1`.
    r.register(m_c2)
    r.register(m_u)
    # Also do not register `m_m`.

    # Resolve by signature.
    assert r.resolve(m_a.signature) == m_a
    assert r.resolve(m_b1.signature) == m_b1
    assert r.resolve(m_b2.signature) == m_b2
    with pytest.raises(plum.AmbiguousLookupError):
        r.resolve(m_c1.signature)
    assert r.resolve(m_c2.signature) == m_c2
    assert r.resolve(m_u.signature) == m_u
    with pytest.raises(plum.NotFoundLookupError):
        r.resolve(m_m.signature)

    # Resolve by type.
    assert r.resolve((A(),)) == m_a
    assert r.resolve((B1(),)) == m_b1
    assert r.resolve((B2(),)) == m_b2
    with pytest.raises(plum.AmbiguousLookupError):
        r.resolve((C1(),))
    assert r.resolve((C2(),)) == m_c2
    assert r.resolve((Unrelated(),)) == m_u
    with pytest.raises(plum.NotFoundLookupError):
        r.resolve((Missing(),))

    # Test that precedence can correctly break the ambiguity.
    m_b1.signature.precedence = 1
    assert r.resolve(m_c1.signature) == m_b1
    m_b2.signature.precedence = 2
    assert r.resolve(m_c1.signature) == m_b2


@pytest.mark.parametrize("warn_redefinition", [False, True])
def test_redefinition_warning(warn_redefinition):
    dispatch = plum.Dispatcher(warn_redefinition=warn_redefinition)

    with warnings.catch_warnings():
        warnings.simplefilter("error")

        @dispatch
        def f(x: int):
            pass

        @dispatch
        def f(x: str):
            pass

        # Warnings are only emitted when all registrations are resolved.
        f._resolve_pending_registrations()

    # Perform the testonce before more after clearing the cache. This reinstantiates
    # the resolver, so we check that `warn_redefinition` is then set correctly.
    for _ in range(2):
        if warn_redefinition:
            with pytest.warns(MethodRedefinitionWarning):

                @dispatch
                def f(x: int):
                    pass

                f._resolve_pending_registrations()
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error")

                @dispatch
                def f(x: int):
                    pass

                f._resolve_pending_registrations()

        dispatch.clear_cache()


def test_redefinition_warning_unwrapping():
    dispatch = plum.Dispatcher(warn_redefinition=True)

    @dispatch
    def f(x: int):
        pass

    # Write and overwrite a method derived from an invoked methods. We test that the
    # unwrapping to find the location of the implementation works correctly.
    f.dispatch_multi((str,))(f.invoke(int))
    f.dispatch_multi((str,))(f.invoke(int))

    with pytest.warns(
        MethodRedefinitionWarning, match=r".*`.*test_resolver.py:[0-9]+`.*" * 2
    ):
        f._resolve_pending_registrations()


def test_not_found_lookup_error_renders_with_signature_target(
    dispatch: plum.Dispatcher,
):
    """NotFoundLookupError raised via .invoke() has a Signature as its target.

    The __rich_console__ method has two branches: one that shows candidate
    suggestions (used when the target is a tuple of runtime arguments) and one
    that simply shows the "could not be resolved" line (used when the target is
    a Signature, because there are no concrete argument values to compute
    distances from).  This test exercises the Signature branch.
    """

    @dispatch
    def f(x: int) -> int:
        return x

    # .invoke(str) looks up by Signature, not by runtime argument types, so
    # NotFoundLookupError.target is a Signature, not a tuple.
    with pytest.raises(plum.NotFoundLookupError) as exc_info:
        f.invoke(str)

    rendered = rich_render(exc_info.value)
    assert "could not be resolved" in rendered


@pytest.mark.incompatible_with_mypyc
def test_resolve_from_does_not_materialise_filter_list():
    """``_resolve_from`` must iterate ``methods`` lazily, not via a temporary list.

    Verified by wrapping ``methods`` in an iterable whose ``__iter__`` raises
    ``RuntimeError`` if called from within a list or generator comprehension frame
    (``<listcomp>`` / ``<genexpr>``).  The bad pattern::

        for method in [m for m in methods if check(m)]:

    causes the comprehension to call ``iter(methods)`` from a ``<listcomp>``
    frame, which our guard detects.  The correct pattern::

        for method in methods:
            if not check(method):
                continue

    calls ``iter(methods)`` directly from ``_resolve_from``'s frame, which
    passes the guard.
    """

    class _NoMaterializeIterable:
        """Raises RuntimeError if iterated from within a list/gen comprehension."""

        def __init__(self, items):
            self._items = items

        def __iter__(self):
            frame = inspect.currentframe()
            caller = frame.f_back if frame is not None else None
            if caller is not None and caller.f_code.co_name in (
                "<listcomp>",
                "<genexpr>",
            ):
                raise RuntimeError(
                    "_resolve_from materialised `methods` inside a comprehension. "
                    "Use direct iteration: `for method in methods:` + "
                    "`if not check(method): continue`."
                )
            return iter(self._items)

    def f():
        pass

    resolver = Resolver()
    m = plum.Method(f, plum.Signature(int))
    resolver.register(m)

    # Wrap the registered methods in the guard and call _resolve_from directly.
    # RuntimeError is raised here if the implementation uses a comprehension.
    guarded = _NoMaterializeIterable(list(resolver.methods))
    result = resolver._resolve_from((1,), guarded)
    assert result is m
