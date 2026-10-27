"""Benchmarks for registration.

Registration is where the type hints are classified. It happens once per method, at
import time of every library that uses Plum.
"""

from typing import Literal

import pytest

import plum
from . import Base, method_on


def _register_and_resolve(hints):
    """Register a method per hint on a fresh function and resolve the registrations."""
    dispatch = plum.Dispatcher()
    for hint in hints:
        f = dispatch(method_on(hint))
    f._resolve_pending_registrations()
    return f


@pytest.mark.benchmark(group="register")
@pytest.mark.parametrize(
    "hints",
    [
        pytest.param((int, str), id="faithful"),
        pytest.param((int | float, str | bytes), id="union"),
        pytest.param((type[Base], type[int]), id="type[X]"),
        pytest.param((Literal["a"], Literal["b"]), id="Literal"),
        pytest.param((tuple[int], tuple[str]), id="parametric"),
    ],
)
def test_register(benchmark, hints):
    """Time registering a set of methods and resolving them for the first time."""
    benchmark(_register_and_resolve, hints)
