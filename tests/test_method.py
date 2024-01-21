import textwrap
from copy import copy

from plum import Dispatcher
from plum.method import Method
from plum.signature import Signature

from .util import rich_render


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


def test_equality():
    m = Method(int, Signature(int), function_name="int", return_type=int)
    assert m == Method(int, Signature(int), function_name="int", return_type=int)
    assert m != Method(float, Signature(int), function_name="int", return_type=int)
    assert m != Method(int, Signature(float), function_name="int", return_type=int)
    assert m != Method(int, Signature(int), function_name="float", return_type=int)
    assert m != Method(int, Signature(int), function_name="int", return_type=float)
    # Methods can also be compared against other objects.
    assert m != 1


def test_repr_simple():
    def f(x, *args) -> float:
        return x

    m = Method(
        f,
        Signature(int, varargs=object),
        return_type=complex,
        function_name="different_name",
    )

    result = (
        f"different_name(x: int, *args: object) -> complex\n"
        f"    <function test_repr_simple.<locals>.f at {hex(id(f))}> @"
    )

    assert repr(m).startswith(result)
    # Also render the fully mismatched version. When rendered to text, that should
    # give the same.
    assert rich_render(m.repr_mismatch({0}, False)).startswith(result)


def test_repr_complex():
    def f(x, *, option, **kw_args) -> float:
        return x

    m = Method(
        f,
        Signature(int, precedence=1),
        return_type=complex,
        function_name="different_name",
    )

    result = (
        f"different_name(x: int, *, option, **kw_args) -> complex\n"
        f"    precedence=1\n"
        f"    <function test_repr_complex.<locals>.f at {hex(id(f))}> @"
    )

    assert repr(m).startswith(result)
    # Also render the fully mismatched version. When rendered to text, that should
    # give the same.
    assert rich_render(m.repr_mismatch({0}, False)).startswith(result)


def test_methodlist_repr(monkeypatch):
    dispatch = Dispatcher()

    @dispatch
    def f(x: int):
        pass

    @dispatch
    def f(x: float):
        pass

    imp1 = f.methods[0].implementation
    imp2 = f.methods[1].implementation

    result = textwrap.dedent(
        f"""
        List of 2 method(s):
            [0] f(x: int)
                <function test_methodlist_repr.<locals>.f at {hex(id(imp1))}> @
            [1] f(x: float)
                <function test_methodlist_repr.<locals>.f at {hex(id(imp2))}> @
        """
    )
    lines = repr(f.methods).strip().splitlines()
    # Remove the lines corresponding to the source of the functions. These are very
    # conveniently broken onto new lines.
    lines = [lines[0], lines[1], lines[2], lines[4], lines[5]]
    assert "\n".join(line.rstrip() for line in lines) == result.strip()
