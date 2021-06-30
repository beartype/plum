import abc

import pytest

from functools import wraps, WRAPPER_UPDATES

from plum import Dispatcher, NotFoundLookupError, AmbiguousLookupError
from plum.type import PromisedType
from tests.test_signature import Num, Re, FP


dispatch = Dispatcher()


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


PromisedCalculator = PromisedType()
PromisedHammer = PromisedType()


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


@dispatch
def f(a: Num):
    return "number"


@dispatch
def f(a: Num, b: Num):
    return "two numbers"


@dispatch
def f(a: Num, b: FP):
    return "a number and a float"


@dispatch
def f(a: Num, b: Num, *cs: Num):
    return "two or more numbers"


@dispatch
def f(a: Num, b: Num, *cs: Re):
    return "two numbers and more reals"


@dispatch
def f(a: FP, b: Num, *cs: Re):
    return "a float, a number, and more reals"


@dispatch
def f(a: Re, b: Num, *cs: FP):
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
    class A(metaclass=abc.ABCMeta):
        @abc.abstractmethod
        def f(self, x):
            pass

    class B(A):
        @dispatch
        def f(self, x: int):
            return x

    # Check that ABC still works.
    with pytest.raises(TypeError):
        A()

    # Check that the abstract method is not dispatched to.
    b = B()
    assert b.f(1) == 1
    with pytest.raises(NotFoundLookupError):
        b.f("1")


def test_self_reference():
    class A:
        @dispatch
        def f(self, x: "A"):
            return "self"

        @dispatch
        def f(self, x: str):
            return "str"

    a = A()

    assert a.f(a) == "self"
    assert a.f("1") == "str"


def test_nested_class():
    class A:
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

    a1 = A()
    a2 = A.A()

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


def test_decorator_in_class():
    class A:
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

    a = A()

    assert a.f(1) == "int"
    assert a.f("1") == "str"


def test_property():
    class A:
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

    a = A()

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
