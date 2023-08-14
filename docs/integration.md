# Integration with Linters and `mypy`

Plum's integration with linters and `mypy` is unfortunately limited.
Properly supporting multiple dispatch in these tools is challenging for a [variety of reasons](https://github.com/python/mypy/issues/11727).
In this section, we collect various patterns in which Plum plays nicely with type checking.

## Overload Support

At the moment, the only know pattern in which Plum produces `mypy`-compliant code uses `typing.overload`.

An example is as follows:

```python
from plum.overload import dispatch, overload


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

In the above, `plum.overload.overload` is `typing_extensions.overload`.
For this pattern to work in all Python versions, you must use `typing_extensions.overload`, not `typing.overload`.
