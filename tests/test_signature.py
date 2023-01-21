import inspect
import operator
import sys
from numbers import Number as Num
from numbers import Rational as Rat
from numbers import Real as Re
from typing import Any, Tuple, Union

import pytest

from plum.signature import Signature as Sig
from plum.signature import (
    _inspect_signature,
    _is_not_empty,
    append_default_args,
    extract_signature,
)
from plum.util import Missing


def test_instantiation_copy():
    s = Sig(
        int,
        int,
        varargs=float,
        return_type=complex,
        precedence=1,
        implementation=lambda *xs: complex(sum(xs)),
    )
    for _ in range(2):
        assert s.types == (int, int)
        assert s.has_varargs
        assert s.varargs == float
        assert s.return_type == complex
        assert s.precedence == 1
        assert s.implementation(1, 2, 3.0) == 6 + 0j
        assert s.is_faithful

        # Test copying.
        s = s.__copy__()

    # Test defaults.
    s = Sig(int, int)
    assert not s.has_varargs
    assert s.varargs == Missing
    assert s.return_type == Any
    assert s.implementation is None

    # Test faithfulness check.
    assert Sig(int, int).is_faithful
    assert Sig(int, int, varargs=int).is_faithful
    assert not Sig(Tuple[int], int, varargs=int).is_faithful
    assert not Sig(int, Tuple[int], varargs=int).is_faithful
    assert not Sig(int, int, varargs=Tuple[int]).is_faithful


@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="Requires Python 3.10 or higher.",
)
def test_instantiation_new_union_syntax():
    assert Sig(float | int) == Sig(Union[float, int])
    assert Sig(Num | Rat) == Sig(Union[Num, Rat])


@pytest.mark.parametrize(
    "sig, expected",
    [
        (
            Sig(),
            f"Signature(varargs={Missing!r}, return_type={Any!r})",
        ),
        (
            Sig(int),
            f"Signature({int!r}, varargs={Missing!r}, return_type={Any!r})",
        ),
        (
            Sig(int, float),
            f"Signature({int!r}, {float!r}, varargs={Missing!r}, return_type={Any!r})",
        ),
        (
            Sig(varargs=int, return_type=float),
            f"Signature(varargs={int!r}, return_type={float!r})",
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


def test_is_not_empty():
    assert not _is_not_empty(inspect.Parameter.empty)
    assert _is_not_empty(None)


def test_inspect_signature():
    assert isinstance(_inspect_signature(lambda x: x), inspect.Signature)
    assert len(_inspect_signature(lambda x: x).parameters) == 1
    assert len(_inspect_signature(operator.itemgetter(1)).parameters) == 1
    assert len(_inspect_signature(operator.attrgetter("x")).parameters) == 1


def assert_signature(f, *types, varargs=Missing, return_type=Any):
    sig = extract_signature(f)
    assert sig.types == types
    assert sig.varargs == varargs
    assert sig.return_type == return_type


def test_extract_signature():
    def f():
        pass

    # Check implementation and precedence.
    assert extract_signature(f).implementation == f
    assert extract_signature(f).precedence == 0
    assert extract_signature(f, precedence=1).precedence == 1

    # Check defaults.
    assert_signature(f)

    # Check a more complex example.

    def f(a: int, b, *c: float, **kw_args: Num) -> Re:
        pass

    assert_signature(f, int, Any, varargs=float, return_type=Re)

    # Check that default values must be right.

    def f_good(a: int = 1):
        pass

    def f_bad(a: int = 1.0):
        pass

    assert_signature(f_good, int)
    with pytest.raises(
        TypeError,
        match=r"Default value `.*` is not an instance of the annotated type `.*`.",
    ):
        extract_signature(f_bad)


def test_append_default_args():
    def f(a: int, b=1, c: float = 1.0, *d: complex, option=None, **other_options):
        pass

    sigs = append_default_args(extract_signature(f), f)
    assert len(sigs) == 4
    assert (sigs[0].types, sigs[0].varargs) == ((int, Any, float), complex)
    assert (sigs[1].types, sigs[1].varargs) == ((int, Any, float), Missing)
    assert (sigs[2].types, sigs[2].varargs) == ((int, Any), Missing)
    assert (sigs[3].types, sigs[3].varargs) == ((int,), Missing)

    # Test that `itemgetter` is supported.
    f = operator.itemgetter(0)
    assert len(append_default_args(extract_signature(f), f)) == 1
