# Integration with Linters and `mypy`

Plum's integration with linters and `mypy` is unfortunately limited.
Properly supporting multiple dispatch in these tools is challenging for a [variety of reasons](https://github.com/python/mypy/issues/11727).
In this section, we collect various patterns in which Plum plays nicely with type checking.

## Overload Support

At the moment, the only known pattern in which Plum produces `mypy`-compliant code uses `typing.overload`.
The idea is to implement and decorate your methods with `typing.overload` instead of `plum.dispatch`.
After all `typing.overload`-decorated methods, add one more method decorated with `plum.dispatch` _without_ an implementation.
This call to `plum.dispatch` will scan for all `typing.overload`-decorated methods and properly add them as Plum methods.


An example is as follows:

```python
from plum import dispatch, overload

__all__ = ["do", "add"]


@overload
def do(x: int) -> int:
    """Do something to an integer.

    Args:
        x (int): An integer.

    Returns:
        int: Another integer.
    """
    return x


@overload
def do(x: str) -> str:
    """Do something to a string.

    Args:
        x (str): A string.

    Returns:
        str: Another string.
    """
    return x


@dispatch
def do(x):
    # Final method without an implementation. This scans for all `overload`-decorated
    # methods and properly adds them as Plum methods.
    pass  


@overload
def add(x: int, y: int) -> int:
    """Add two integers.

    Args:
        x (int): First integer.
        y (int): Second integer.

    Returns:
        int: Sum of `x` and `y`.
    """
    return x + y


@overload
def add(x: float, y: float) -> float:
    """Add two floats.

    Args:
        x (float): First float.
        y (float): Second float.

    Returns:
        float: Sum of `x` and `y`.
    """
    return x + y


@dispatch
def add(x):
    pass
```

In the above, for Python versions prior to 3.11, `plum.overload` is `typing_extensions.overload`.
For this pattern to work in Python versions prior to 3.11, you must use `typing_extensions.overload`, not `typing.overload`.
By importing `overload` from `plum`, you will always use the correct `overload`.

This pattern diverges from the normal use of `typing.overload` in two ways.
First, usually `typing.overload` is used to specify additional type signatures that do not contain an implementation.
In the above pattern, the `typing.overload`-decorated methods _do_ have implementations.
Second, after all `typing.overload`, usually one implements a normal Python function that implements all overloaded type signatures.
In the above pattern, this final method uses `plum.dispatch` and does _not_ contain an implementation.
