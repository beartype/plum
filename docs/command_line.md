# Command Line Configuration Options

## `PLUM_SIMPLE_DOC`

Set `PLUM_SIMPLE_DOC=1` to prevent Plum from concatenating the docstrings of all methods.
Consider

```python
from plum import dispatch


@dispatch.abstract
def do(x):
    """Do something."""


@dispatch
def do(x: int) -> int:
    """Do something with integers."""
```

The usual output of `help(f)` is as follows:
```
Help on Function in module __main__:

do(x)
    Do something.

    ---------------------------

    do(x: int) -> int

    Do something with integers.
```

With `PLUM_SIMPLE_DOC=1`, `help(f)` only shows the docstring of the first registered method:
```
Help on Function in module __main__:

do(x)
    Do something.
```
