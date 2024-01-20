from time import time

import rich

__all__ = ["benchmark", "rich_render"]


def benchmark(f, args, n=1000, burn=0, setup=lambda: None):
    """Benchmark the performance of a function `f` called with arguments
    `args` in microseconds.

    Args:
        f (function): Function to benchmark.
        args (tuple): Argument to call `f` with.
        n (int, optional): Repetitions. Defaults to 1000.
        burn (int, optional): Perform so many repetitions before timing.
        setup (function, optional): Call this function before every call to `f`.

    Returns:
        float: Average execution time in milliseconds.
    """
    # Perform burn-in.
    for _ in range(burn):
        setup()
        f(*args)
    # Perform timing.
    durations = []
    for _ in range(n):
        setup()
        start = time()
        f(*args)
        durations.append(time() - start)
    return sum(durations) * 1e6 / n


def rich_render(x: object) -> str:
    """Render a :mod:`rich` object to text.

    Args:
        x (object): Object to render.

    Returns:
        str: Text representation of `x`.
    """
    console = rich.get_console()
    with console.capture() as capture:
        console.print(x)
    return capture.get()
