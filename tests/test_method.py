from copy import copy

from plum.method import Method
from plum.signature import Signature


def test_instantiation_copy():
    def _f(arg1) -> float:
        return arg1

    sig = Signature(int)

    m = Method(
        _f,
        sig,
        return_type=complex,
        function_name="prova",
    )
    for _ in range(2):
        assert m.function_name == "prova"
        assert m.signature == sig
        assert m.return_type == complex
        assert m.implementation == _f

        # Test copying.
        assert m == copy(m)
        m = copy(m)

    m2 = Method(
        _f,
        sig,
        return_type=complex,
        function_name="prova",
    )
    assert m2 == m
    assert hash(m2) == hash(m)

    m3 = Method(
        _f,
        Signature(float),
        return_type=complex,
        function_name="prova",
    )
    assert m2 != m3
    assert hash(m2) != hash(m3)


def test_autodetect_name_return():
    def _f(arg1) -> float:
        return arg1

    sig = Signature(int)

    m = Method(
        _f,
        sig,
    )
    assert m.function_name == "_f"
    assert m.return_type == float


def test_repr():
    def _f(arg1) -> float:
        return arg1

    sig = Signature(int)

    m = Method(
        _f,
        Signature(int),
        return_type=complex,
        function_name="prova",
    )

    assert repr(m) == (
        f"Method(function_name='prova', signature={sig},"
        f" return_type={complex}, impl={_f})"
    )
