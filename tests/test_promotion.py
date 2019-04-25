# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import convert, add_conversion_method, add_promotion_rule, promote, \
    conversion_method
from . import eq, raises
from .test_tuple import Num, Re, FP


def save_convert_methods():
    convert._resolve_pending_registrations()
    return convert.methods.copy()


def restore_convert_methods(methods):
    convert.methods = methods


def test_conversion():
    convert_methods = save_convert_methods()

    # Test basic conversion.
    yield eq, convert(1.0, float), 1.0
    yield eq, convert(1.0, object), 1.0
    yield raises, TypeError, lambda: convert(1.0, int)

    # Test conversion with inheritance.
    r = Re()
    yield eq, convert(r, Re), r
    yield eq, convert(r, Num), r
    yield raises, TypeError, lambda: convert(r, FP)

    # Test `add_conversion_method`.
    add_conversion_method(float, int, lambda _: 2.0)
    yield eq, convert(1.0, float), 1.0
    yield eq, convert(1.0, object), 1.0
    yield eq, convert(1.0, int), 2.0

    # Test `conversion_method`.
    @conversion_method(Num, FP)
    def num_to_fp(x):
        return 3.0

    yield eq, convert(r, Re), r
    yield eq, convert(r, Num), r
    yield eq, convert(r, FP), 3.0

    restore_convert_methods(convert_methods)


def test_promotion():
    convert_methods = save_convert_methods()

    yield eq, promote(1), (1,)
    yield eq, promote(1.), (1.,)
    yield eq, promote(1, 1), (1, 1)
    yield eq, promote(1., 1.), (1., 1.)
    yield eq, promote(1, 1, 1), (1, 1, 1)
    yield eq, promote(1., 1., 1.), (1., 1., 1.)
    yield raises, TypeError, lambda: promote(1, 1.)
    yield raises, TypeError, lambda: promote(1., 1)

    add_promotion_rule(int, float, float)

    yield raises, TypeError, lambda: promote(1, 1.)
    yield raises, TypeError, lambda: promote(1., 1)

    add_conversion_method(int, float, float)

    yield eq, promote(1, 1.), (1., 1.)
    yield eq, promote(1, 1, 1.), (1., 1., 1.)
    yield eq, promote(1., 1., 1), (1., 1., 1.)

    yield raises, TypeError, lambda: promote(1, '1')
    yield raises, TypeError, lambda: promote('1', 1)
    yield raises, TypeError, lambda: promote(1., '1')
    yield raises, TypeError, lambda: promote('1', 1.)

    add_promotion_rule(str, {int, float}, {int, float})
    add_conversion_method(str, {int, float}, float)

    yield eq, promote(1, '1', '1'), (1., 1., 1.)
    yield eq, promote('1', 1, 1), (1., 1., 1.)
    yield eq, promote(1., '1', 1), (1., 1., 1.)
    yield eq, promote('1', 1., 1), (1., 1., 1.)

    add_promotion_rule(str, int, float)
    add_promotion_rule(str, float, float)
    add_conversion_method(str, float, lambda x: 'lel')

    yield eq, promote(1, '1', 1.), (1., 'lel', 1.)
    yield eq, promote('1', 1, 1.), ('lel', 1., 1.)
    yield eq, promote(1., '1', 1), (1., 'lel', 1.)
    yield eq, promote('1', 1., '1'), ('lel', 1., 'lel')

    restore_convert_methods(convert_methods)


def test_inheritance():
    convert_methods = save_convert_methods()

    add_promotion_rule(Num, FP, Num)
    add_promotion_rule(Num, Re, Num)
    add_promotion_rule(FP, Re, Num)
    add_conversion_method(FP, Num, lambda x: 'Num from FP')
    add_conversion_method(Re, Num, lambda x: 'Num from Re')

    n = Num()
    yield eq, promote(n, FP()), (n, 'Num from FP')
    yield eq, promote(Re(), n), ('Num from Re', n)
    yield eq, promote(Re(), FP()), ('Num from Re', 'Num from FP')

    restore_convert_methods(convert_methods)
