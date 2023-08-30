from typing import Tuple

import pytest

from plum.resolver import AmbiguousLookupError, NotFoundLookupError, Resolver
from plum.signature import Signature


def test_initialisation():
    r = Resolver([])
    # Without any registered signatures, the resolver should be faithful.
    assert r.is_faithful


def test_register():
    # Test that faithfulness is tracked correctly.
    r = Resolver([Signature(int), Signature(float)])
    assert r.is_faithful
    r = Resolver([Signature(int), Signature(float), Signature(Tuple[int])])
    assert not r.is_faithful

    # Test that signatures can be replaced.
    assert len(r) == 3
    new_s = Signature(float)
    assert r.signatures[1] is not new_s
    r = Resolver([Signature(int), Signature(float), Signature(Tuple[int]), new_s])
    assert len(r) == 3
    assert r.signatures[1] is new_s


def test_len():
    r = Resolver([])
    assert len(r) == 0
    r = Resolver([Signature(int)])
    assert len(r) == 1
    r = Resolver([Signature(int), Signature(float)])
    assert len(r) == 2
    r = Resolver([Signature(int), Signature(float), Signature(float)])
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

    r = Resolver(
        [
            s_b1,
            # Import this after `s_b1` to test all branches.
            s_a,
            s_b2,
            # Do not register `s_c1`.
            s_c2,
            s_u,
            # Also do not register `s_m`.
        ]
    )
    # Resolve by signature.
    assert r._resolve(s_a) == s_a
    assert r._resolve(s_b1) == s_b1
    assert r._resolve(s_b2) == s_b2
    with pytest.raises(AmbiguousLookupError):
        r._resolve(s_c1)
    assert r._resolve(s_c2) == s_c2
    assert r._resolve(s_u) == s_u
    with pytest.raises(NotFoundLookupError):
        r._resolve(s_m)

    # Resolve by type.
    assert r._resolve((A(),)) == s_a
    assert r._resolve((B1(),)) == s_b1
    assert r._resolve((B2(),)) == s_b2
    with pytest.raises(AmbiguousLookupError):
        r._resolve((C1(),))
    assert r._resolve((C2(),)) == s_c2
    assert r._resolve((Unrelated(),)) == s_u
    with pytest.raises(NotFoundLookupError):
        r._resolve((Missing(),))

    # Test that precedence can correctly break the ambiguity.
    s_b1.precedence = 1
    assert r._resolve(s_c1) == s_b1
    s_b2.precedence = 2
    assert r._resolve(s_c1) == s_b2
