import inspect
import operator
from numbers import Number as Num
from numbers import Real as Re
from typing import Any, Tuple

import pytest

from plum.signature import Signature as Sig
from plum.signature import append_default_args, inspect_signature
from plum.util import Missing


def test_instantiation_copy():
    s = Sig(
        int,
        int,
        varargs=float,
        precedence=1,
    )
    for _ in range(2):
        assert s.types == (int, int)
        assert s.has_varargs
        assert s.varargs == float
        assert s.precedence == 1
        assert s.is_faithful

        # Test copying.
        s = s.__copy__()

    # Test defaults.
    s = Sig(int, int)
    assert not s.has_varargs
    assert s.varargs == Missing

    # Test faithfulness check.
    assert Sig(int, int).is_faithful
    assert Sig(int, int, varargs=int).is_faithful
    assert not Sig(Tuple[int], int, varargs=int).is_faithful
    assert not Sig(int, Tuple[int], varargs=int).is_faithful
    assert not Sig(int, int, varargs=Tuple[int]).is_faithful


def _impl(x, y, *z):
    return str(x)


@pytest.mark.parametrize(
    "sig, expected",
    [
        (
            Sig(),
            "Signature()",
        ),
        (
            Sig(int),
            "Signature(int)",
        ),
        (
            Sig(int, float),
            "Signature(int, float)",
        ),
        (
            Sig(int, float, varargs=complex),
            "Signature(int, float, varargs=complex)",
        ),
        (
            Sig(int, float, varargs=complex),
            "Signature(int, float, varargs=complex)",
        ),
        (
            Sig(int, float, varargs=complex, precedence=1),
            "Signature(int, float, varargs=complex, precedence=1)",
        ),
        (
            Sig(
                int,
                float,
                varargs=complex,
                precedence=1,
            ),
            "Signature(int, float, varargs=complex, precedence=1)",
        ),
    ],
)
def test_repr(sig, expected):
    assert repr(sig) == expected


def test_hash():
    assert hash(Sig(int)) == hash(Sig(int))
    sigs = {Sig(int), Sig(int, int), Sig(int, int, varargs=int)}
    assert len(sigs) == 3


def test_expand_varargs():
    # Case of no variable arguments:
    assert Sig(int, int).expand_varargs(3) == (int, int)

    # Case of variable arguments:
    s = Sig(int, int, varargs=float)
    assert s.expand_varargs(2) == (int, int)
    assert s.expand_varargs(3) == (int, int, float)
    assert s.expand_varargs(4) == (int, int, float, float)


def test_comparison():
    # Variable arguments shortcuts:
    assert not Sig(varargs=int) <= Sig()
    assert not Sig(varargs=Num) <= Sig(varargs=int)

    # Expandability shortcuts:
    assert not Sig(int) <= Sig(int, int)
    assert not Sig(int) <= Sig(int, int, varargs=int)
    assert not Sig(int, int, varargs=int) <= Sig(int)

    # Test expansion:
    assert Sig(varargs=int) <= Sig(Re, varargs=Re)
    assert Sig(int, varargs=int) <= Sig(Re, varargs=Re)
    assert Sig(int, int, varargs=int) <= Sig(Re, varargs=Re)

    assert not Sig(varargs=Num) <= Sig(Re, varargs=Re)
    assert not Sig(Num, varargs=int) <= Sig(Re, varargs=Re)
    assert not Sig(int, int, varargs=Num) <= Sig(Re, varargs=Re)

    assert Sig(float, varargs=int) <= Sig(float, Re, varargs=Re)
    assert Sig(float, int, varargs=int) <= Sig(float, Re, varargs=Re)
    assert Sig(float, int, int, varargs=int) <= Sig(float, Re, varargs=Re)


def test_match():
    assert Sig(int).match((1,))
    assert Sig(int, int).match((1, 2))
    assert Sig(int, varargs=int).match((1,))
    assert Sig(int, varargs=int).match((1, 2))
    assert Sig(int, varargs=int).match((1, 2, 3))

    # Wrong type:
    assert not Sig(int).match((1.0,))
    assert not Sig(int, int).match((1, 2.0))
    assert not Sig(int, varargs=int).match((1.0,))
    assert not Sig(int, varargs=int).match((1, 2.0))
    assert not Sig(int, varargs=int).match((1, 2, 3.0))

    # Wrong number:
    assert not Sig(int).match((1, 2))
    assert not Sig(int, int).match((1,))
    assert not Sig(int, varargs=int).match(())


def test_inspect_signature():
    assert isinstance(inspect_signature(lambda x: x), inspect.Signature)
    assert len(inspect_signature(lambda x: x).parameters) == 1
    assert len(inspect_signature(operator.itemgetter(1)).parameters) == 1
    assert len(inspect_signature(operator.attrgetter("x")).parameters) == 1


def assert_signature(f, *types, varargs=Missing):
    sig = Sig.from_callable(f)
    assert sig.types == types
    assert sig.varargs == varargs


def test_signature_from_callable():
    def f():
        pass

    # Check precedence.
    assert Sig.from_callable(f).precedence == 0
    assert Sig.from_callable(f, precedence=1).precedence == 1

    # Check defaults.
    assert_signature(f)

    # Check a more complex example.

    def f(a: int, b, *c: float, **kw_args: Num) -> Re:
        pass

    assert_signature(f, int, Any, varargs=float)

    # Check that default values must be right.

    def f_good(a: int = 1):
        pass

    def f_bad(a: int = 1.0):
        pass

    assert_signature(f_good, int)
    with pytest.raises(
        TypeError,
        match=r"Default value `1.0` is not an instance of the annotated type `int`.",
    ):
        Sig.from_callable(f_bad)


def test_append_default_args():
    def f(a: int, b=1, c: float = 1.0, *d: complex, option=None, **other_options):
        pass

    sigs = append_default_args(Sig.from_callable(f), f)
    assert len(sigs) == 3
    assert (sigs[0].types, sigs[0].varargs) == ((int, Any, float), complex)
    assert (sigs[1].types, sigs[1].varargs) == ((int, Any), Missing)
    assert (sigs[2].types, sigs[2].varargs) == ((int,), Missing)

    # Test that `itemgetter` is supported.
    f = operator.itemgetter(0)
    assert len(append_default_args(Sig.from_callable(f), f)) == 1
