import sys
import textwrap
import warnings

import pytest

import plum
from plum._method import Method
from plum._resolver import (
    MethodRedefinitionWarning,
    Resolver,
    _document,
    _render_function_call,
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
    r.register(Method(f, plum.Signature(int)))
    r.register(Method(f, plum.Signature(float)))
    assert r.is_faithful
    r.register(Method(f, plum.Signature(tuple[int])))
    assert not r.is_faithful

    # Test that signatures can be replaced.
    new_m = Method(f, plum.Signature(float))
    assert len(r) == 3
    assert r.methods[1] is not new_m
    r.register(new_m)
    assert len(r) == 3
    assert r.methods[1] is new_m

    # Test the edge case that should never happen.
    r.methods[2] = Method(f, plum.Signature(float))
    with pytest.raises(
        AssertionError,
        match=r"(?i)the added method `(.*)` is equal to 2 existing methods",
    ):
        r.register(Method(f, plum.Signature(float)))


def test_len():
    def f(x):
        return x

    r = Resolver()
    assert len(r) == 0
    r.register(Method(f, plum.Signature(int)))
    assert len(r) == 1
    r.register(Method(f, plum.Signature(float)))
    assert len(r) == 2
    r.register(Method(f, plum.Signature(float)))
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

    m_a = Method(f, plum.Signature(A))
    m_b1 = Method(f, plum.Signature(B1))
    m_b2 = Method(f, plum.Signature(B2))
    m_c1 = Method(f, plum.Signature(C1))
    m_c2 = Method(f, plum.Signature(C2))
    m_u = Method(f, plum.Signature(Unrelated))
    m_m = Method(f, plum.Signature(Missing))

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
        MethodRedefinitionWarning,
        match=r".*`.*test_resolver.py:[0-9]+`.*" * 2,
    ):
        f._resolve_pending_registrations()
