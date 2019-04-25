# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from . import Referentiable, Reference, Promise, ResolutionError
from . import eq, raises


def test_promise():
    p = Promise()
    yield raises, ResolutionError, lambda: p.resolve()
    p.deliver(1)
    yield eq, p.resolve(), 1


def test_reference():
    class A(Referentiable):
        pass

    ref = Reference()
    ref.pos -= 1  # Reference is created *outside* the class definition.
    yield eq, ref.resolve(), A
    ref.pos += 1
    yield raises, ResolutionError, lambda: ref.resolve()
