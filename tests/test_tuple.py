# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Tuple as Tu
from . import eq, neq, lt, le, ge, gt, raises, call


def test_corner_cases():
    yield raises, TypeError, lambda: Tu([int], int)
    yield raises, TypeError, lambda: Tu([int, str])
    yield raises, RuntimeError, lambda: Tu(1)
    yield raises, RuntimeError, lambda: Tu(int).varargs_type


class Num(object):
    pass


class Re(Num):
    pass


class FP(Re):
    pass


def test_tuple():
    yield le, Tu(Num, FP), Tu(Num, FP)
    yield ge, Tu(Num, FP), Tu(Num, FP)
    yield eq, Tu(Num, FP), Tu(Num, FP)
    yield lt, Tu(Num, Re), Tu(Num, Num)
    yield gt, Tu(Num, Num), Tu(Num, Re)
    yield lt, Tu(Num, Re), Tu(Num, Num)
    yield lt, Tu(FP, Num), Tu(Num, Num)
    yield lt, Tu(FP, FP), Tu(Num, Num)


def test_tuple_varargs():
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
