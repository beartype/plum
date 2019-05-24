# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import pytest

from plum import (
    Self,
    Dispatcher,
    PromisedType,
    Referentiable,
    NotFoundLookupError,
    AmbiguousLookupError
)
from .test_signature import Num, Re, FP


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

    assert device.do() == 'doing nothing'
    assert device.do(FP(), FP()) == 'doing a real and a number'
    assert device.do(Re(), Re()) == 'doing a real and a number'
    assert device.do(Num(), Re()) == 'doing two numbers'
    assert device.do(device) == 'doing a device'


def test_inheritance():
    device = Device()
    calc = Calculator(1)
    hammer = Hammer()

    assert device + calc == 'unknown device'
    assert Device.__add__(device, calc) == 'unknown device'
    assert calc + device == 'unknown device'
    assert Calculator.__add__(calc, device) == 'unknown device'
    assert device + hammer == 'unknown device'
    assert Device.__add__(device, hammer) == 'unknown device'
    assert hammer + device == 'unknown device'
    assert Hammer.__add__(hammer, device) == 'unknown device'
    assert hammer + hammer == 'super hammer'
    assert Hammer.__add__(hammer, hammer) == 'super hammer'
    assert calc + calc == 'super calculator'
    assert Calculator.__add__(calc, calc) == 'super calculator'
    assert hammer + calc == 'destroyed calculator'
    assert Hammer.__add__(hammer, calc) == 'destroyed calculator'
    assert calc + hammer == 'destroyed calculator'
    assert Calculator.__add__(calc, hammer) == 'destroyed calculator'
    assert calc.compute(ComputableObject()) == 'result'
    assert calc.compute(object, ComputableObject()) == 'a result'
    assert calc.compute(ComputableObject(), object) == 'another result'


def test_inheritance_exceptions():
    calc = Calculator()
    o = ComputableObject()

    # Test instantiation.
    with pytest.raises(NotFoundLookupError):
        Calculator('1')

    # Test method lookup.
    with pytest.raises(NotFoundLookupError):
        calc.compute(1)

    # Test method ambiguity.
    with pytest.raises(AmbiguousLookupError):
        calc.compute(o, o)
    assert calc.compute(object, o) == 'a result'
    assert calc.compute(o, object) == 'another result'


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
    assert f() == 'fallback'
    assert f(Num()) == 'number'
    assert f(Num(), object) == 'fallback'
    assert f(object, Num()) == 'fallback'
    assert f(Num(), Num()) == 'two numbers'
    assert f(Num(), Num(), Num()) == 'two or more numbers'
    with pytest.raises(LookupError):
        f(FP(), FP(), FP())
    with pytest.raises(LookupError):
        f(FP(), Re(), FP())
    with pytest.raises(LookupError):
        f(FP(), Num(), FP())
    assert f(FP(), Num(), Re()) == 'a float, a number, and more reals'
    assert f(Re(), Num(), FP()) == 'a real, a number, and more floats'
    assert f(Num(), FP(), FP()) == 'two numbers and more reals'
    assert f(Num(), Num(), FP()) == 'two numbers and more reals'
    with pytest.raises(LookupError):
        f(FP(), FP())
