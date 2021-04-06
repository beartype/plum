from time import time


def benchmark(f, args, n=1000):
    """Benchmark the performance of a function `f` called with arguments
    `args` in microseconds.

    Args:
        f (function): Function to benchmark.
        args (tuple): Argument to call `f` with.
        n (int): Repetitions.
    """
    start = time()
    for i in range(n):
        f(*args)
    dur = time() - start
    return dur * 1e6 / n
