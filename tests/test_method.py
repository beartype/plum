from copy import copy

from plum.method import Method
from plum.signature import Signature


def test_instantiation_copy():
    def f(x) -> float:
        return x

    def f2(x) -> float:
        return x

    sig = Signature(int)

    m = Method(
        f,
        sig,
        return_type=complex,
        function_name="different_name",
    )
    for _ in range(2):
        assert m.function_name == "different_name"
        assert m.signature == sig
        assert m.return_type == complex
        assert m.implementation == f

        # Test copying.
        assert m == copy(m)
        m = copy(m)

    m_equal = Method(
        f,
        sig,
        return_type=complex,
        function_name="different_name",
    )
    assert m == m_equal
    assert hash(m) == hash(m_equal)

    for m_unequal in [
        Method(
            f2,
            sig,
            return_type=complex,
            function_name="different_name",
        ),
        Method(
            f,
            Signature(float),
            return_type=complex,
            function_name="different_name",
        ),
        Method(
            f,
            sig,
            return_type=int,
            function_name="different_name",
        ),
        Method(
            f,
            sig,
            return_type=int,
            function_name="another_name",
        ),
    ]:
        assert m != m_unequal
        assert hash(m) != hash(m_unequal)


def test_autodetect_name_return():
    def f(x) -> float:
        return x

    sig = Signature(int)

    m = Method(f, sig)
    assert m.function_name == "f"
    assert m.return_type == float


def test_repr():
    def f(x) -> float:
        return x

    m = Method(
        f,
        Signature(int),
        return_type=complex,
        function_name="different_name",
    )

    str2 = (
        "different_name(x: int) -> complex\n"
        f"    <function test_repr.<locals>.f at {hex(id(f))}> @"
    )

    for a, b in zip(repr(m), str2):
        print(a, "|", b, "|", a == b)

    assert repr(m).startswith(str2)
