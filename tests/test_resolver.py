from typing import Tuple

import pytest

from plum.resolver import AmbiguousLookupError, NotFoundLookupError, Resolver
from plum.signature import Signature


def test_initialisation():
    r = Resolver()
    # Without any registered signatures, the resolver should be faithful.
    assert r.is_faithful


def test_register():
    r = Resolver()

    # Test that faithfulness is tracked correctly.
    r.register(Signature(int))
    r.register(Signature(float))
    assert r.is_faithful
    r.register(Signature(Tuple[int]))
    assert not r.is_faithful

    # Test that signatures can be replaced.
    new_s = Signature(float)
    assert len(r) == 3
    assert r.signatures[1] is not new_s
    r.register(new_s)
    assert len(r) == 3
    assert r.signatures[1] is new_s

    # Test the edge case that should never happen.
    r.signatures[2] = Signature(float)
    with pytest.raises(
        AssertionError,
        match=r"(?i)the added signature `(.*)` is equal to 2 existing signatures",
    ):
        r.register(Signature(float))


def test_len():
    r = Resolver()
    assert len(r) == 0
    r.register(Signature(int))
    assert len(r) == 1
    r.register(Signature(float))
    assert len(r) == 2
    r.register(Signature(float))
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

    s_a = Signature(A)
    s_b1 = Signature(B1)
    s_b2 = Signature(B2)
    s_c1 = Signature(C1)
    s_c2 = Signature(C2)
    s_u = Signature(Unrelated)
    s_m = Signature(Missing)

    r = Resolver()
    r.register(s_b1)
    # Import this after `s_b1` to test all branches.
    r.register(s_a)
    r.register(s_b2)
    # Do not register `s_c1`.
    r.register(s_c2)
    r.register(s_u)
    # Also do not register `s_m`.

    # Resolve by signature.
    assert r.resolve(s_a) == s_a
    assert r.resolve(s_b1) == s_b1
    assert r.resolve(s_b2) == s_b2
    with pytest.raises(AmbiguousLookupError):
        r.resolve(s_c1)
    assert r.resolve(s_c2) == s_c2
    assert r.resolve(s_u) == s_u
    with pytest.raises(NotFoundLookupError):
        r.resolve(s_m)

    # Resolve by type.
    assert r.resolve((A(),)) == s_a
    assert r.resolve((B1(),)) == s_b1
    assert r.resolve((B2(),)) == s_b2
    with pytest.raises(AmbiguousLookupError):
        r.resolve((C1(),))
    assert r.resolve((C2(),)) == s_c2
    assert r.resolve((Unrelated(),)) == s_u
    with pytest.raises(NotFoundLookupError):
        r.resolve((Missing(),))

    # Test that precedence can correctly break the ambiguity.
    s_b1.precedence = 1
    assert r.resolve(s_c1) == s_b1
    s_b2.precedence = 2
    assert r.resolve(s_c1) == s_b2
