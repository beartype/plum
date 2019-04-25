# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Tuple as Tu, Type
from . import ok, eq, neq, lt, le, ge, gt, raises, call


def test_instantiation():
    yield raises, TypeError, lambda: Tu([int], int)
    yield raises, TypeError, lambda: Tu([int, str])


class Num(object):
    pass


class Re(Num):
    pass


class FP(Re):
    pass


def test_properties():
    yield eq, repr(Tu(Num)), '({!r})'.format(Type(Num))
    yield eq, hash(Tu(Num)), hash(Tu(Num))
    yield neq, hash(Tu(Num)), hash(Type(Num))
    yield eq, len(Tu(Num)), 1
    yield eq, len(Tu(Num, [Num])), 1


def test_comparability():
    yield ok, Tu(Num).is_comparable(Tu(FP))
    yield ok, not Tu(Num).is_comparable(Tu(int))


def test_comparisons():
    yield le, Tu(Num, FP), Tu(Num, FP)
    yield ge, Tu(Num, FP), Tu(Num, FP)
    yield eq, Tu(Num, FP), Tu(Num, FP)
    yield lt, Tu(Num, Re), Tu(Num, Num)
    yield gt, Tu(Num, Num), Tu(Num, Re)
    yield lt, Tu(Num, Re), Tu(Num, Num)
    yield lt, Tu(FP, Num), Tu(Num, Num)
    yield lt, Tu(FP, FP), Tu(Num, Num)


def test_varargs_properties():
    yield eq, \
          Tu(Num, Num, [Num]).expand_varargs_to(Tu(Num)), \
          (Type(Num), Type(Num))
    yield eq, \
          Tu(Num, [Num]).expand_varargs_to(Tu(Num, Num, Num)), \
          (Type(Num), Type(Num), Type(Num))
    yield eq, Tu(Num).expand_varargs_to(Tu(Num, Num)), (Type(Num),)
    yield eq, Tu(Num, [FP]).base, (Type(Num),)
    yield ok, Tu([Num]).has_varargs()
    yield ok, not Tu(Num).has_varargs()
    yield eq, Tu([Num]).varargs_type, Type(Num)
    yield raises, RuntimeError, lambda: Tu(Num).varargs_type


def test_varargs_comparisons():
    yield lt, Tu(Num, [Num]), Tu([object])
    yield gt, Tu(Num, [Num]), Tu(Num)
    yield lt, Tu(FP, [Num]), Tu(Num, [Num])
    yield lt, Tu(FP, [FP]), Tu(FP, [Num])
    yield le, Tu(FP, [FP]), Tu(FP, [Num])
    yield neq, Tu(FP, [FP]), Tu(FP, [Num])
    yield lt, Tu(FP, Num), Tu(FP, Num, [Num])
    yield lt, Tu(Num, Num), Tu(Num, [Num])
    yield call, Tu(Num, Num), 'is_comparable', (Tu(FP, [FP]),), False
    yield call, Tu(Num, [FP]), 'is_comparable', (Tu(Num, Num),), False
    yield eq, Tu([Num]), Tu(Num, [Num])
    yield gt, Tu([Num]), Tu(Re, [Num])
    yield eq, Tu(Num, [Num]), Tu(Num, Num, Num, [Num])


def test_tuple_union():
    yield eq, Tu({Num, Num}), Tu({Num})
    yield eq, Tu({FP, Num}), Tu({Num})
    yield ge, Tu({FP, Num}), Tu({Re})
    yield lt, Tu({FP}), Tu({Num, Re})
