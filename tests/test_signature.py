import pytest

from plum.signature import Signature as Sig
from plum.type import Type, VarArgs, Union


def test_instantiation():
    with pytest.raises(TypeError):
        Sig(VarArgs(int), int)
    with pytest.raises(TypeError):
        Sig(VarArgs(int, str))


class Num:
    pass


class Re(Num):
    pass


class FP(Re):
    pass


def test_properties():
    assert hash(Sig(Num)) == hash(Sig(Num))
    assert hash(Sig(Num)) != hash(Type(Num))
    assert len(Sig(Num)) == 1
    assert len(Sig(Num, VarArgs(Num))) == 1


def test_representation():
    assert repr(Sig()) == "Signature()"
    assert repr(Sig(Num, Re)) == f"Signature({Type(Num)!r}, {Type(Re)!r})"


def test_comparability():
    assert Sig(Num).is_comparable(Sig(FP))
    assert not Sig(Num).is_comparable(Sig(int))


def test_comparisons():
    assert Sig(Num, FP) <= Sig(Num, FP)
    assert Sig(Num, FP) >= Sig(Num, FP)
    assert Sig(Num, FP) == Sig(Num, FP)
    assert Sig(Num, Re) < Sig(Num, Num)
    assert Sig(Num, Num) > Sig(Num, Re)
    assert Sig(Num, Re) < Sig(Num, Num)
    assert Sig(FP, Num) < Sig(Num, Num)
    assert Sig(FP, FP) < Sig(Num, Num)


def test_varargs_properties():
    expanded_sig = Sig(Num, Num, VarArgs(Num)).expand_varargs_to(Sig(Num))
    assert expanded_sig == (Type(Num), Type(Num))
    expanded_sig = Sig(Num, VarArgs(Num)).expand_varargs_to(Sig(Num, Num, Num))
    assert expanded_sig == (Type(Num), Type(Num), Type(Num))
    assert Sig(Num).expand_varargs_to(Sig(Num, Num)) == (Type(Num),)
    assert Sig(Num, VarArgs(FP)).base == (Type(Num),)
    assert Sig(VarArgs(Num)).has_varargs()
    assert not Sig(Num).has_varargs()
    assert Sig(VarArgs(Num)).varargs_type == Type(Num)
    with pytest.raises(RuntimeError):
        Sig(Num).varargs_type


def test_varargs_comparisons():
    assert Sig(Num, VarArgs(Num)) < Sig(VarArgs(object))
    assert Sig(Num, VarArgs(Num)) > Sig(Num)
    assert Sig(FP, VarArgs(Num)) < Sig(Num, VarArgs(Num))
    assert Sig(FP, VarArgs(FP)) < Sig(FP, VarArgs(Num))
    assert Sig(FP, VarArgs(FP)) <= Sig(FP, VarArgs(Num))
    assert Sig(FP, VarArgs(FP)) != Sig(FP, VarArgs(Num))
    assert Sig(FP, Num) < Sig(FP, Num, VarArgs(Num))
    assert Sig(Num, Num) < Sig(Num, VarArgs(Num))
    assert not Sig(Num, Num).is_comparable(Sig(FP, VarArgs(FP)))
    assert not Sig(Num, VarArgs(FP)).is_comparable(Sig(Num, Num))
    assert Sig(VarArgs(Num)) == Sig(Num, VarArgs(Num))
    assert Sig(VarArgs(Num)) > Sig(Re, VarArgs(Num))
    assert Sig(Num, VarArgs(Num)) == Sig(Num, Num, Num, VarArgs(Num))


def test_union():
    assert Sig(Union(Num, Num)) == Sig(Union(Num))
    assert Sig(Union(FP, Num)) == Sig(Union(Num))
    assert Sig(Union(FP, Num)) >= Sig(Union(Re))
    assert Sig(Union(FP)) < Sig(Union(Num, Re))
