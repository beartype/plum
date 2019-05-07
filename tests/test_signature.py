# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Signature as Sig, Type
from . import ok, eq, neq, lt, le, ge, gt, raises, call


def test_instantiation():
    yield raises, TypeError, lambda: Sig([int], int)
    yield raises, TypeError, lambda: Sig([int, str])


class Num(object):
    pass


class Re(Num):
    pass


class FP(Re):
    pass


def test_properties():
    yield eq, repr(Sig(Num)), '({!r})'.format(Type(Num))
    yield eq, hash(Sig(Num)), hash(Sig(Num))
    yield neq, hash(Sig(Num)), hash(Type(Num))
    yield eq, len(Sig(Num)), 1
    yield eq, len(Sig(Num, [Num])), 1


def test_comparability():
    yield ok, Sig(Num).is_comparable(Sig(FP))
    yield ok, not Sig(Num).is_comparable(Sig(int))


def test_comparisons():
    yield le, Sig(Num, FP), Sig(Num, FP)
    yield ge, Sig(Num, FP), Sig(Num, FP)
    yield eq, Sig(Num, FP), Sig(Num, FP)
    yield lt, Sig(Num, Re), Sig(Num, Num)
    yield gt, Sig(Num, Num), Sig(Num, Re)
    yield lt, Sig(Num, Re), Sig(Num, Num)
    yield lt, Sig(FP, Num), Sig(Num, Num)
    yield lt, Sig(FP, FP), Sig(Num, Num)


def test_varargs_properties():
    yield eq, \
          Sig(Num, Num, [Num]).expand_varargs_to(Sig(Num)), \
          (Type(Num), Type(Num))
    yield eq, \
          Sig(Num, [Num]).expand_varargs_to(Sig(Num, Num, Num)), \
          (Type(Num), Type(Num), Type(Num))
    yield eq, Sig(Num).expand_varargs_to(Sig(Num, Num)), (Type(Num),)
    yield eq, Sig(Num, [FP]).base, (Type(Num),)
    yield ok, Sig([Num]).has_varargs()
    yield ok, not Sig(Num).has_varargs()
    yield eq, Sig([Num]).varargs_type, Type(Num)
    yield raises, RuntimeError, lambda: Sig(Num).varargs_type


def test_varargs_comparisons():
    yield lt, Sig(Num, [Num]), Sig([object])
    yield gt, Sig(Num, [Num]), Sig(Num)
    yield lt, Sig(FP, [Num]), Sig(Num, [Num])
    yield lt, Sig(FP, [FP]), Sig(FP, [Num])
    yield le, Sig(FP, [FP]), Sig(FP, [Num])
    yield neq, Sig(FP, [FP]), Sig(FP, [Num])
    yield lt, Sig(FP, Num), Sig(FP, Num, [Num])
    yield lt, Sig(Num, Num), Sig(Num, [Num])
    yield call, Sig(Num, Num), 'is_comparable', (Sig(FP, [FP]),), False
    yield call, Sig(Num, [FP]), 'is_comparable', (Sig(Num, Num),), False
    yield eq, Sig([Num]), Sig(Num, [Num])
    yield gt, Sig([Num]), Sig(Re, [Num])
    yield eq, Sig(Num, [Num]), Sig(Num, Num, Num, [Num])


def test_union():
    yield eq, Sig({Num, Num}), Sig({Num})
    yield eq, Sig({FP, Num}), Sig({Num})
    yield ge, Sig({FP, Num}), Sig({Re})
    yield lt, Sig({FP}), Sig({Num, Re})
