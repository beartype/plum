# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import pytest

from plum import Signature as Sig, Type


def test_instantiation():
    with pytest.raises(TypeError):
        Sig([int], int)
    with pytest.raises(TypeError):
        Sig([int, str])


class Num(object):
    pass


class Re(Num):
    pass


class FP(Re):
    pass


def test_properties():
    assert repr(Sig(Num)) == '({!r})'.format(Type(Num))
    assert hash(Sig(Num)) == hash(Sig(Num))
    assert hash(Sig(Num)) != hash(Type(Num))
    assert len(Sig(Num)) == 1
    assert len(Sig(Num, [Num])) == 1


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
    assert Sig(Num, Num, [Num]).expand_varargs_to(Sig(Num)) == (
        Type(Num), Type(Num))
    assert Sig(Num, [Num]).expand_varargs_to(Sig(Num, Num, Num)) == (
        Type(Num), Type(Num), Type(Num))
    assert Sig(Num).expand_varargs_to(Sig(Num, Num)) == (Type(Num),)
    assert Sig(Num, [FP]).base == (Type(Num),)
    assert Sig([Num]).has_varargs()
    assert not Sig(Num).has_varargs()
    assert Sig([Num]).varargs_type == Type(Num)
    with pytest.raises(RuntimeError):
        Sig(Num).varargs_type


def test_varargs_comparisons():
    assert Sig(Num, [Num]) < Sig([object])
    assert Sig(Num, [Num]) > Sig(Num)
    assert Sig(FP, [Num]) < Sig(Num, [Num])
    assert Sig(FP, [FP]) < Sig(FP, [Num])
    assert Sig(FP, [FP]) <= Sig(FP, [Num])
    assert Sig(FP, [FP]) != Sig(FP, [Num])
    assert Sig(FP, Num) < Sig(FP, Num, [Num])
    assert Sig(Num, Num) < Sig(Num, [Num])
    assert not Sig(Num, Num).is_comparable(Sig(FP, [FP]))
    assert not Sig(Num, [FP]).is_comparable(Sig(Num, Num))
    assert Sig([Num]) == Sig(Num, [Num])
    assert Sig([Num]) > Sig(Re, [Num])
    assert Sig(Num, [Num]) == Sig(Num, Num, Num, [Num])


def test_union():
    assert Sig({Num, Num}) == Sig({Num})
    assert Sig({FP, Num}) == Sig({Num})
    assert Sig({FP, Num}) >= Sig({Re})
    assert Sig({FP}) < Sig({Num, Re})
