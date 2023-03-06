from typing import Tuple

import numpy as np

from plum import Dispatcher, dispatch
from tests.util import benchmark


def f(x):
    pass


@dispatch
def g(x: int):
    pass


@dispatch
def g(x: str):
    pass


dur_native = benchmark(f, (1,), n=1000, burn=10)
dur_plum = benchmark(g, (1,), n=1000, burn=10)
factor = int(np.round(dur_plum / dur_native))

print("# Function Calls")
print("Native call: {:6.2f} us ({:.1f} x)".format(dur_native, 1))
print("Plum call:   {:6.2f} us ({:.1f} x)".format(dur_plum, factor))
print()


def f2(x):
    pass


@dispatch
def g2(x: Tuple[int]):
    pass


@dispatch
def g2(x: Tuple[str]):
    pass


dur_native = benchmark(f2, ((1,),), n=1000, burn=10)
dur_plum = benchmark(g2, ((1,),), n=1000, burn=10)
factor = int(np.round(dur_plum / dur_native))

print("# Parametric Function Calls")
print("Native call: {:6.2f} us ({:.1f} x)".format(dur_native, 1))
print("Plum call:   {:6.2f} us ({:.1f} x)".format(dur_plum, factor))
print()


class A:
    def __call__(self, x):
        pass

    def go(self, x):
        pass


class B:
    _dispatch = Dispatcher()

    @_dispatch
    def __call__(self, x: int):
        pass

    @_dispatch
    def __call__(self, x: str):
        pass

    @_dispatch
    def go(self, x: int):
        pass

    @_dispatch
    def go(self, x: str):
        pass


a = A()
b = B()

dur_native = benchmark(a, (1,), n=1000, burn=10)
dur_plum = benchmark(b, (1,), n=1000, burn=10)
factor = int(np.round(dur_plum / dur_native))

print("# Class Calls")
print("Native call: {:6.2f} us ({:.1f} x)".format(dur_native, 1))
print("Plum call:   {:6.2f} us ({:.1f} x)".format(dur_plum, factor))
print()

dur_native = benchmark(lambda x: a.go(x), (1,), n=1000, burn=10)
dur_plum = benchmark(lambda x: b.go(x), (1,), n=1000, burn=10)
factor = int(np.round(dur_plum / dur_native))

print("# Class Attribute Calls")
print("Native call: {:6.2f} us ({:.1f} x)".format(dur_native, 1))
print("Plum call:   {:6.2f} us ({:.1f} x)".format(dur_plum, factor))
