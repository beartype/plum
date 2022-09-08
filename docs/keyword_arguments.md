# Keyword Arguments and Default Values

Default arguments can be used.
The type annotation must match the default value otherwise an error is thrown.
As the example below illustrates, different default values can be used for different methods:

```python
from plum import dispatch

@dispatch
def f(x: int, y: int = 3):
    return y


@dispatch
def f(x: float, y: float = 3.0):
    return y
```

```python
>>> f(1)
3

>>> f(1.0)
3.0

>>> f(1.0, 4.0)
4.0

>>> f(1.0, y=4.0)
4.0
```

Keyword-only arguments, separated by an asterisk from the other arguments, can
also be used, but are *not* dispatched on.

Example:

```python
from plum import dispatch

@dispatch
def f(x, *, option="a"):
    return option
```

```python
>>> f(1)
'a'

>>> f(1, option="b")
'b'

>>> f(1, "b")  # This will not work, because `option` must be given as a keyword.
NotFoundLookupError: For function "f", signature Signature(builtins.int, builtins.str) could not be resolved.
```
