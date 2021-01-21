import abc

import pytest

from plum import (
    Self,
    Dispatcher,
    PromisedType,
    Referentiable,
    NotFoundLookupError,
    AmbiguousLookupError,
)
from .test_signature import Num, Re, FP


class ComputableObject:
    pass


class Device(metaclass=Referentiable):
    _dispatch = Dispatcher(in_class=Self)

    @_dispatch
    def __init__(self):
        pass

    @_dispatch
    def do(self, x: Num, y: Num):
        return "doing two numbers"

    @_dispatch
    def do(self):
        return "doing nothing"

    @_dispatch
    def do(self, other: Self):
        return "doing a device"

    @_dispatch
    def do(self, x: Re, y: Num):
        return "doing a real and a number"

    def __add__(self, other):
        return "unknown device"

    def __radd__(self, other):
        return other + self

    @_dispatch
    def compute(self, a, b: ComputableObject):
        return "a result"

    @_dispatch
    def compute(self, a: ComputableObject, b):
        return "another result"


PromisedCalculator = PromisedType()
PromisedHammer = PromisedType()


class Hammer(Device):
    _dispatch = Dispatcher(in_class=Self)

    @_dispatch
    def __add__(self, other: PromisedHammer):
        return "super hammer"

    @_dispatch
    def __add__(self, other: PromisedCalculator):
        return "destroyed calculator"


class Calculator(Device):
    _dispatch = Dispatcher(in_class=Self)

    @_dispatch
    def __init__(self, size: int):
        self.size = size
        Device.__init__(self)

    @_dispatch
    def __add__(self, other: PromisedCalculator):
        return "super calculator"

    @_dispatch
    def __add__(self, other: PromisedHammer):
        return "destroyed calculator"

    @_dispatch
    def compute(self, obj: ComputableObject):
        return "result"


PromisedCalculator.deliver(Calculator)
PromisedHammer.deliver(Hammer)


def test_method_dispatch():
    device = Device()

    assert device.do() == "doing nothing"
    assert device.do(FP(), FP()) == "doing a real and a number"
    assert device.do(Re(), Re()) == "doing a real and a number"
    assert device.do(Num(), Re()) == "doing two numbers"
    assert device.do(device) == "doing a device"


def test_inheritance():
    device = Device()
    calc = Calculator(1)
    hammer = Hammer()

    assert device + calc == "unknown device"
    assert Device.__add__(device, calc) == "unknown device"
    assert calc + device == "unknown device"
    assert Calculator.__add__(calc, device) == "unknown device"
    assert device + hammer == "unknown device"
    assert Device.__add__(device, hammer) == "unknown device"
    assert hammer + device == "unknown device"
    assert Hammer.__add__(hammer, device) == "unknown device"
    assert hammer + hammer == "super hammer"
    assert Hammer.__add__(hammer, hammer) == "super hammer"
    assert calc + calc == "super calculator"
    assert Calculator.__add__(calc, calc) == "super calculator"
    assert hammer + calc == "destroyed calculator"
    assert Hammer.__add__(hammer, calc) == "destroyed calculator"
    assert calc + hammer == "destroyed calculator"
    assert Calculator.__add__(calc, hammer) == "destroyed calculator"
    assert calc.compute(ComputableObject()) == "result"
    assert calc.compute(object, ComputableObject()) == "a result"
    assert calc.compute(ComputableObject(), object) == "another result"


def test_inheritance_exceptions():
    calc = Calculator()
    o = ComputableObject()

    # Test instantiation.
    with pytest.raises(NotFoundLookupError):
        Calculator("1")

    # Test method lookup.
    with pytest.raises(NotFoundLookupError):
        calc.compute(1)

    # Test method ambiguity.
    with pytest.raises(AmbiguousLookupError):
        calc.compute(o, o)
    assert calc.compute(object, o) == "a result"
    assert calc.compute(o, object) == "another result"


_dispatch = Dispatcher()


@_dispatch
def f(a: Num):
    return "number"


@_dispatch
def f(a: Num, b: Num):
    return "two numbers"


@_dispatch
def f(a: Num, b: FP):
    return "a number and a float"


@_dispatch
def f(a: Num, b: Num, *cs: Num):
    return "two or more numbers"


@_dispatch
def f(a: Num, b: Num, *cs: Re):
    return "two numbers and more reals"


@_dispatch
def f(a: FP, b: Num, *cs: Re):
    return "a float, a number, and more reals"


@_dispatch
def f(a: Re, b: Num, *cs: FP):
    return "a real, a number, and more floats"


@_dispatch
def f(*args):
    return "fallback"


def test_varargs():
    assert f() == "fallback"
    assert f(Num()) == "number"
    assert f(Num(), object) == "fallback"
    assert f(object, Num()) == "fallback"
    assert f(Num(), Num()) == "two numbers"
    assert f(Num(), Num(), Num()) == "two or more numbers"
    with pytest.raises(LookupError):
        f(FP(), FP(), FP())
    with pytest.raises(LookupError):
        f(FP(), Re(), FP())
    with pytest.raises(LookupError):
        f(FP(), Num(), FP())
    assert f(FP(), Num(), Re()) == "a float, a number, and more reals"
    assert f(Re(), Num(), FP()) == "a real, a number, and more floats"
    assert f(Num(), FP(), FP()) == "two numbers and more reals"
    assert f(Num(), Num(), FP()) == "two numbers and more reals"
    with pytest.raises(LookupError):
        f(FP(), FP())


def test_abc_abstractmethod():
    class A(metaclass=Referentiable):
        @abc.abstractmethod
        def f(self, x):
            pass

    class B(A):
        _dispatch = Dispatcher(in_class=Self)

        @_dispatch
        def f(self, x: int):
            return x

    b = B()

    # Check that the abstract method is not dispatched to.
    assert b.f(1) == 1
    with pytest.raises(NotFoundLookupError):
        b.f("1")
