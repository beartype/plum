import abc

import pytest

from plum import Dispatcher, Referentiable, Self, Promise, ResolutionError


def test_promise():
    p = Promise()
    with pytest.raises(ResolutionError):
        p.resolve()
    p.deliver(1)
    assert p.resolve() == 1


def test_reference():
    class A:
        pass

    ref = Self()
    ref._type_parameter -= 1  # Reference is created *outside* the class definition.
    assert ref.resolve() is A
    ref._type_parameter += 1
    with pytest.raises(ResolutionError):
        ref.resolve()


def test_referentiable():
    class A(metaclass=Referentiable):
        dispatch = Dispatcher()

        @dispatch
        def do(self: Self):
            return self

    a = A()
    assert a.do() is a


def test_referentiable_metaclass_wrapping():
    class A(metaclass=Referentiable(abc.ABCMeta)):
        @abc.abstractmethod
        def do(self):
            pass

    with pytest.raises(TypeError):
        A()
