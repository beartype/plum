# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import pytest

from plum import Referentiable, Reference, Promise, ResolutionError


def test_promise():
    p = Promise()
    with pytest.raises(ResolutionError):
        p.resolve()
    p.deliver(1)
    assert p.resolve() == 1


def test_reference():
    class A(Referentiable):
        pass

    ref = Reference()
    ref.pos -= 1  # Reference is created *outside* the class definition.
    assert ref.resolve() == A
    ref.pos += 1
    with pytest.raises(ResolutionError):
        ref.resolve()
