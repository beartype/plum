# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Self, Dispatcher, PromisedType, \
    Referentiable, NotFoundLookupError, AmbiguousLookupError
from . import eq, raises
from .test_tuple import Num, Re, FP


class ComputableObject(object):
    pass


class Device(Referentiable):
    _dispatch = Dispatcher(in_class=Self)

    @_dispatch()
    def __init__(self):
        pass

    @_dispatch(Num, Num)
    def do(self, x, y):
        return 'doing two numbers'

    @_dispatch()
    def do(self):
        return 'doing nothing'

    @_dispatch(Self)
    def do(self, other):
        return 'doing a device'

    @_dispatch(Re, Num)
    def do(self, x, y):
        return 'doing a real and a number'

    def __add__(self, other):
        return 'unknown device'

    def __radd__(self, other):
        return other + self

    @_dispatch(object, ComputableObject)
    def compute(self, a, b):
        return 'a result'

    @_dispatch(ComputableObject, object)
    def compute(self, a, b):
        return 'another result'


PromisedCalculator = PromisedType()
PromisedHammer = PromisedType()


class Hammer(Device, Referentiable):
    _dispatch = Dispatcher(in_class=Self)

    @_dispatch(PromisedHammer)
    def __add__(self, other):
        return 'super hammer'

    @_dispatch(PromisedCalculator)
    def __add__(self, other):
        return 'destroyed calculator'


class Calculator(Device, Referentiable):
    _dispatch = Dispatcher(in_class=Self)

    @_dispatch(int)
    def __init__(self, size):
        self.size = size
        Device.__init__(self)

    @_dispatch(PromisedCalculator)
    def __add__(self, other):
        return 'super calculator'

    @_dispatch(PromisedHammer)
    def __add__(self, other):
        return 'destroyed calculator'

    @_dispatch(ComputableObject)
    def compute(self, obj):
        return 'result'


PromisedCalculator.deliver(Calculator)
PromisedHammer.deliver(Hammer)


def test_method_dispatch():
    device = Device()

    yield eq, device.do(), 'doing nothing'
    yield eq, device.do(FP(), FP()), 'doing a real and a number'
    yield eq, device.do(Re(), Re()), 'doing a real and a number'
    yield eq, device.do(Num(), Re()), 'doing two numbers'
    yield eq, device.do(device), 'doing a device'


def test_inheritance():
    device = Device()
    calc = Calculator(1)
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

    # Test instantiation.
    yield raises, NotFoundLookupError, lambda: Calculator('1')

    # Test method lookup.
    yield raises, NotFoundLookupError, lambda: calc.compute(1)

    # Test method ambiguity.
    yield raises, AmbiguousLookupError, lambda: calc.compute(o, o)
    yield eq, calc.compute(object, o), 'a result'
    yield eq, calc.compute(o, object), 'another result'


_dispatch = Dispatcher()


@_dispatch(Num)
def f(a):
    return 'number'


@_dispatch(Num, Num)
def f(a, b):
    return 'two numbers'


@_dispatch(Num, FP)
def f(a, b):
    return 'a number and a float'


@_dispatch(Num, Num, [Num])
def f(a, b, *cs):
    return 'two or more numbers'


@_dispatch(Num, Num, [Re])
def f(a, b, *cs):
    return 'two numbers and more reals'


@_dispatch(FP, Num, [Re])
def f(a, b, c, *ds):
    return 'a float, a number, and more reals'


@_dispatch(Re, Num, [FP])
def f(a, b, c, *ds):
    return 'a real, a number, and more floats'


@_dispatch([])
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
