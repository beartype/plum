import abc

import pytest

from plum import Referentiable, Reference, Promise, ResolutionError


def test_promise():
    p = Promise()
    with pytest.raises(ResolutionError):
        p.resolve()
    p.deliver(1)
    assert p.resolve() == 1


def test_reference():
    class A(metaclass=Referentiable):
        pass

    ref = Reference()
    ref.pos -= 1  # Reference is created *outside* the class definition.
    assert ref.resolve() == A
    ref.pos += 1
    with pytest.raises(ResolutionError):
        ref.resolve()


def test_referentiable_metaclass_wrapping():
    class A(metaclass=Referentiable(abc.ABCMeta)):
        @abc.abstractmethod
        def do(self):
            pass

    with pytest.raises(TypeError):
        A()
