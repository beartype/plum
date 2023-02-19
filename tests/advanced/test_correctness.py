from functools import wraps

import pytest

from plum import AmbiguousLookupError, Dispatcher, NotFoundLookupError
from plum.type import PromisedType

dispatch = Dispatcher()


class Num:
    pass


class Re(Num):
    pass


class Rat(Re):
    pass


class ComputableObject:
    pass


class Device:
    @dispatch
    def __init__(self):
        pass

    @dispatch
    def do(self, x: Num, y: Num):
        return "doing two numbers"

    @dispatch
    def do(self):
        return "doing nothing"

    @dispatch
    def do(self, other: "Device"):
        return "doing a device"

    @dispatch
    def do(self, x: Re, y: Num):
        return "doing a real and a number"

    def __add__(self, other):
        return "unknown device"

    def __radd__(self, other):
        return other + self

    @dispatch
    def compute(self, a, b: ComputableObject):
        return "a result"

    @dispatch
    def compute(self, a: ComputableObject, b):
        return "another result"


PromisedCalculator = PromisedType("Calculator")
PromisedHammer = PromisedType("Hammer")


class Hammer(Device):
    @dispatch
    def __add__(self, other: PromisedHammer):
        return "super hammer"

    @dispatch
    def __add__(self, other: PromisedCalculator):
        return "destroyed calculator"


class Calculator(Device):
    @dispatch
    def __init__(self, size: int):
        self.size = size
        Device.__init__(self)

    @dispatch
    def __add__(self, other: PromisedCalculator):
        return "super calculator"

    @dispatch
    def __add__(self, other: PromisedHammer):
        return "destroyed calculator"

    @dispatch
    def compute(self, obj: ComputableObject):
        return "result"


PromisedCalculator.deliver(Calculator)
PromisedHammer.deliver(Hammer)


def test_method_dispatch():
    device = Device()

    assert device.do() == "doing nothing"
    assert device.do(Rat(), Rat()) == "doing a real and a number"
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


@dispatch
def f(a: Num):
    return "number"


@dispatch
def f(a: Num, b: Num):
    return "two numbers"


@dispatch
def f(a: Num, b: Rat):
    return "a number and a float"


@dispatch
def f(a: Num, b: Num, *cs: Num):
    return "two or more numbers"


@dispatch
def f(a: Num, b: Num, *cs: Re):
    return "two numbers and more reals"


@dispatch
def f(a: Rat, b: Num, *cs: Re):
    return "a float, a number, and more reals"


@dispatch
def f(a: Re, b: Num, *cs: Rat):
    return "a real, a number, and more floats"


@dispatch
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
        f(Rat(), Rat(), Rat())
    with pytest.raises(LookupError):
        f(Rat(), Re(), Rat())
    with pytest.raises(LookupError):
        f(Rat(), Num(), Rat())
    assert f(Rat(), Num(), Re()) == "a float, a number, and more reals"
    assert f(Re(), Num(), Rat()) == "a real, a number, and more floats"
    assert f(Num(), Rat(), Rat()) == "two numbers and more reals"
    assert f(Num(), Num(), Rat()) == "two numbers and more reals"
    with pytest.raises(LookupError):
        f(Rat(), Rat())


class A2:
    @dispatch
    def f(self, x: "A2"):
        return "self"

    @dispatch
    def f(self, x: str):
        return "str"


def test_self_reference():
    a = A2()

    assert a.f(a) == "self"
    assert a.f("1") == "str"


class A3:
    @dispatch
    def f(self, x: int):
        return "int1"

    class A:
        @dispatch
        def f(self, x: int):
            return "int2"

        @dispatch
        def f(self, x: str):
            return "str2"

    @dispatch
    def f(self, x: str):
        return "str1"


def test_nested_class():
    a1 = A3()
    a2 = A3.A()

    assert a1.f(1) == "int1"
    assert a1.f("1") == "str1"

    assert a2.f(1) == "int2"
    assert a2.f("1") == "str2"


def dec(f):
    @wraps(f)
    def f_wrapped(*args, **kw_args):
        return f(*args, **kw_args)

    return f_wrapped


def test_decorator():
    dispatch = Dispatcher()

    @dec
    @dispatch
    @dec
    def g(x: int):
        return "int"

    @dec
    @dispatch
    @dec
    def g(x: str):
        return "str"

    assert g(1) == "int"
    assert g("1") == "str"


class A4:
    @dec
    @dispatch
    @dec
    def f(self, x: int):
        return "int"

    # Cannot use a decorator before `dispatch` here!
    @dispatch
    @dec
    def f(self, x: str):
        return "str"


def test_decorator_in_class():
    a = A4()

    assert a.f(1) == "int"
    assert a.f("1") == "str"


class A5:
    @property
    def name(self):
        return "name"

    @name.setter
    @dispatch
    def name(self, x: str):
        return "str"

    # This setup requires that the class has another method!
    @dispatch
    def f(self):
        pass


def test_property():
    a = A5()

    assert a.name == "name"
    a.name = "another name"
    with pytest.raises(NotFoundLookupError):
        a.name = 1


def test_none():
    dispatch = Dispatcher()

    @dispatch
    def f(x: None) -> None:
        return x

    assert f(None) is None
