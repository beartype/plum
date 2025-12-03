import numpy as np

from util import benchmark

import plum


def f(x):
    pass


@plum.dispatch
def g(x: int):
    pass


@plum.dispatch
def g(x: str):
    pass


dur_native = benchmark(f, (1,), n=1000, burn=10)
dur_plum = benchmark(g, (1,), n=1000, burn=10)
factor = int(np.round(dur_plum / dur_native))

print("# Function Calls")
print(f"Native call: {dur_native:6.2f} us ({1:.1f} x)")
print(f"Plum call:   {dur_plum:6.2f} us ({factor:.1f} x)")
print()


def f2(x):
    pass


@plum.dispatch
def g2(x: tuple[int]):
    pass


@plum.dispatch
def g2(x: tuple[str]):
    pass


dur_native = benchmark(f2, ((1,),), n=1000, burn=10)
dur_plum = benchmark(g2, ((1,),), n=1000, burn=10)
factor = int(np.round(dur_plum / dur_native))

print("# Parametric Function Calls")
print(f"Native call: {dur_native:6.2f} us ({1:.1f} x)")
print(f"Plum call:   {dur_plum:6.2f} us ({factor:.1f} x)")
print()


class A:
    def __call__(self, x):
        pass

    def go(self, x):
        pass


class B:
    _dispatch = plum.Dispatcher()

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
print(f"Native call: {dur_native:6.2f} us ({1:.1f} x)")
print(f"Plum call:   {dur_plum:6.2f} us ({factor:.1f} x)")
print()

dur_native = benchmark(lambda x: a.go(x), (1,), n=1000, burn=10)
dur_plum = benchmark(lambda x: b.go(x), (1,), n=1000, burn=10)
factor = int(np.round(dur_plum / dur_native))

print("# Class Attribute Calls")
print(f"Native call: {dur_native:6.2f} us ({1:.1f} x)")
print(f"Plum call:   {dur_plum:6.2f} us ({factor:.1f} x)")
