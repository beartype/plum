from plum import dispatch
from tests.util import benchmark
import numpy as np


def f(x): pass


@dispatch(object)
def g(x): pass


@dispatch(int)
def g(x): pass


dur_native = benchmark(f, (1,))
dur_first_plum = benchmark(g, (1,), n=1)
dur_plum = benchmark(g, (1,))

print('Native call:     {:6.2f} us ({:d} x)'.format(dur_native, 1))
print('First plum call: {:6.2f} us ({:d} x)'
      ''.format(dur_first_plum, int(np.round(dur_first_plum / dur_native))))
print('Plum call:       {:6.2f} us ({:d} x)'
      ''.format(dur_plum, int(np.round(dur_plum / dur_native))))
