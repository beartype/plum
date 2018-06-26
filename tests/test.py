# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Tuple as Tu, Function, Self, Dispatcher, PromisedType, \
    Referentiable, NotFoundLookupError, AmbiguousLookupError, \
    ResolutionError, dispatch, Union, as_type
from . import eq, neq, lt, le, ge, gt, raises, call, ok


def test_corner_cases():
    yield raises, ResolutionError, lambda: PromisedType().resolve()
    yield raises, ResolutionError, lambda: Self().resolve()
    yield raises, TypeError, lambda: Tu([int], int)
    yield raises, TypeError, lambda: Tu([int, str])
    yield raises, RuntimeError, lambda: Tu(1)
    yield raises, RuntimeError, lambda: Tu(int).varargs_type
    yield raises, RuntimeError, lambda: as_type({int, str}).mro()

    dispatch = Dispatcher()

    @dispatch(int)
    def f(x): pass

    @dispatch(int)
    def f(x): pass

    yield raises, RuntimeError, lambda: f(1)


class Num(object):
    pass


class Re(Num):
    pass


class FP(Re):
    pass


def test_function():
    f = Function(lambda x: x)
    for signature in [Tu(Num, Num), Tu(Num, Re),
                      Tu(FP, Num), Tu(FP, FP)]:
        f.register(signature, None)

    yield call, f, 'resolve', (Tu(Re, Re),), Tu(Num, Re)
    yield call, f, 'resolve', (Tu(Re, FP),), Tu(Num, Re)
    yield raises, LookupError, lambda: f.resolve(Tu(FP, Re))

    # Test dynamic extension of the function.
    yield raises, LookupError, lambda: f.resolve(Tu(int))

    @f.extend(int)
    def f(x): pass

    yield call, f, 'resolve', (Tu(int),), Tu(int)


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


class ComputableObject(object):
    pass


class Device(Referentiable):
    dispatch = Dispatcher(in_class=Self)

    @dispatch(Num, Num)
    def do(self, x, y):
        return 'doing two numbers'

    @dispatch()
    def do(self):
        return 'doing nothing'

    @dispatch(Self)
    def do(self, other):
        return 'doing a device'

    @dispatch(Re, Num)
    def do(self, x, y):
        return 'doing a real and a number'

    def __add__(self, other):
        return 'unknown device'

    def __radd__(self, other):
        return other + self

    @dispatch(object, ComputableObject)
    def compute(self, a, b):
        return 'a result'

    @dispatch(ComputableObject, object)
    def compute(self, a, b):
        return 'another result'


PromisedCalculator = PromisedType()
PromisedHammer = PromisedType()


class Hammer(Device, Referentiable):
    dispatch = Dispatcher(in_class=Self)

    @dispatch(PromisedHammer)
    def __add__(self, other):
        return 'super hammer'

    @dispatch(PromisedCalculator)
    def __add__(self, other):
        return 'destroyed calculator'


class Calculator(Device, Referentiable):
    dispatch = Dispatcher(in_class=Self)

    @dispatch(PromisedCalculator)
    def __add__(self, other):
        return 'super calculator'

    @dispatch(PromisedHammer)
    def __add__(self, other):
        return 'destroyed calculator'

    @dispatch(ComputableObject)
    def compute(self, obj):
        return 'result'


PromisedCalculator.deliver(Calculator)
PromisedHammer.deliver(Hammer)


def test_dispatch():
    device = Device()

    yield eq, device.do(), 'doing nothing'
    yield eq, device.do(FP(), FP()), 'doing a real and a number'
    yield eq, device.do(Re(), Re()), 'doing a real and a number'
    yield eq, device.do(Num(), Re()), 'doing two numbers'
    yield eq, device.do(device), 'doing a device'


def test_inheritance():
    device = Device()
    calc = Calculator()
    hammer = Hammer()

    yield eq, device + calc, 'unknown device'
    yield eq, Device.__add__(device, calc), 'unknown device'
    yield eq, calc + device, 'unknown device'
    yield eq, Calculator.__add__(calc, device), 'unknown device'
    yield eq, device + hammer, 'unknown device'
    yield eq, Device.__add__(device, hammer), 'unknown device'
    yield eq, hammer + device, 'unknown device'
    yield eq, Hammer.__add__(hammer, device), 'unknown device'
    yield eq, hammer + hammer, 'super hammer'
    yield eq, Hammer.__add__(hammer, hammer), 'super hammer'
    yield eq, calc + calc, 'super calculator'
    yield eq, Calculator.__add__(calc, calc), 'super calculator'
    yield eq, hammer + calc, 'destroyed calculator'
    yield eq, Hammer.__add__(hammer, calc), 'destroyed calculator'
    yield eq, calc + hammer, 'destroyed calculator'
    yield eq, Calculator.__add__(calc, hammer), 'destroyed calculator'
    yield eq, calc.compute(ComputableObject()), 'result'
    yield eq, calc.compute(object, ComputableObject()), 'a result'
    yield eq, calc.compute(ComputableObject(), object), 'another result'


def test_inheritance_exceptions():
    calc = Calculator()
    o = ComputableObject()

    yield raises, NotFoundLookupError, lambda: calc.compute(1)
    yield raises, AmbiguousLookupError, lambda: calc.compute(o, o)
    yield eq, calc.compute(object, o), 'a result'
    yield eq, calc.compute(o, object), 'another result'


@dispatch(Num)
def f(a):
    return 'number'


@dispatch(Num, Num)
def f(a, b):
    return 'two numbers'


@dispatch(Num, FP)
def f(a, b):
    return 'a number and a float'


@dispatch(Num, Num, [Num])
def f(a, b, *cs):
    return 'two or more numbers'


@dispatch(Num, Num, [Re])
def f(a, b, *cs):
    return 'two numbers and more reals'


@dispatch(FP, Num, [Re])
def f(a, b, c, *ds):
    return 'a float, a number, and more reals'


@dispatch(Re, Num, [FP])
def f(a, b, c, *ds):
    return 'a real, a number, and more floats'


@dispatch([])
def f(*args):
    return 'fallback'


def test_varargs():
    yield eq, f(), 'fallback'
    yield eq, f(Num()), 'number'
    yield eq, f(Num(), object), 'fallback'
    yield eq, f(object, Num()), 'fallback'
    yield eq, f(Num(), Num()), 'two numbers'
    yield eq, f(Num(), Num(), Num()), 'two or more numbers'
    yield raises, LookupError, lambda: f(FP(), FP(), FP())
    yield raises, LookupError, lambda: f(FP(), Re(), FP())
    yield raises, LookupError, lambda: f(FP(), Num(), FP())
    yield eq, f(FP(), Num(), Re()), 'a float, a number, and more reals'
    yield eq, f(Re(), Num(), FP()), 'a real, a number, and more floats'
    yield eq, f(Num(), FP(), FP()), 'two numbers and more reals'
    yield eq, f(Num(), Num(), FP()), 'two numbers and more reals'
    yield raises, LookupError, lambda: f(FP(), FP())


def test_multi():
    dispatch = Dispatcher()

    @dispatch(object)
    def f(x):
        return 'fallback'

    @dispatch.multi([int], [str])
    def f(x):
        return 'int or str'

    yield eq, f(1), 'int or str'
    yield eq, f('1'), 'int or str'
    yield eq, f(1.), 'fallback'


def test_instance_check():
    t = Union(int, str)
    yield ok, isinstance(1, t)
    yield ok, isinstance('1', t)
    yield ok, not isinstance(1., t)
