# Integration with Linters and `mypy`

Plum's integration with linters and `mypy` is unfortunately limited.
Properly supporting multiple dispatch in these tools is challenging for a [variety of reasons](https://github.com/python/mypy/issues/11727).
In this section, we collect various patterns in which Plum plays nicely with type checking.

## Overload Support

At the moment, the only know pattern in which Plum produces `mypy`-compliant code uses `typing.overload`.

An example is as follows:

```python
from plum import dispatch, overload


@overload
def f(x: int) -> int:
    return x


@overload
def f(x: str) -> str:
    return x


@dispatch
def f(x):
    pass
```

In the above, for Python versions prior to 3.11, `plum.overload` is `typing_extensions.overload`.
For this pattern to work in Python versions prior to 3.11, you must use `typing_extensions.overload`, not `typing.overload`.
By importing `overload` from `plum`, you will always use the correct `overload`.
