# Ways to Dispatch

You can add new methods to functions in a variety of ways.
We list them all below.

## Abstract Function Definitions

A function can be abstractly defined using `dispatch.abstract`.
When a function is abstractly defined, the function is created, but no methods
are defined.

Example usage:

```python
from numbers import Number

from plum import dispatch


@dispatch.abstract
def f(x: Number, y: Number):
    """Multiply two numbers."""


@dispatch
def f(x: float, y: float):
    """Multiply two floats."""
    return x * y


@dispatch
def f(x: int, y: int):
    """Multiply two ints."""
    return x * y
```

Then

```python
>>> f.methods  # No implementation for `Number`s!
List of 2 method(s):
    [0] f(x: float, y: float)
        <function f at ...> @ ...
    [1] f(x: int, y: int)
        <function f at ...> @ ...
```

and calling `help(f)` produces

```
Help on Function in module __main__:

f(x: numbers.Number, y: numbers.Number)
    Multiply two numbers.

    ---------------------

    f(x: float, y: float)

    Multiply two floats.

    ---------------------

    f(x: int, y: int)

    Multiply two ints.
```

## Extend a Function From Another Package

`Function.dispatch` can be used to extend a particular function from an external
package:

% skip: start "`package` is not a real package."

```python
from package import f


@f.dispatch
def f(x: int):
    return "new behaviour"
```

```python
>>> f(1.0)
'old behaviour'

>>> f(1)
'new behaviour'
```

% skip: end

## Directly Invoke a Method

`Function.invoke` can be used to invoke a method given types of the arguments:

```python
from plum import dispatch


@dispatch
def f(x: int):
    return "int"


@dispatch
def f(x: str):
    return "str"
```

```python
>>> f(1)
'int'

>>> f("1")
'str'

>>> f.invoke(int)("1")
'int'

>>> f.invoke(str)(1)
'str'
```

## Define Multiple Methods at Once

`Dispatcher.multi` can be used to implement multiple methods at once:

```python
from typing import Union

from plum import dispatch


@dispatch.multi((int, int), (float, float))
def add(x: Union[int, float], y: Union[int, float]):
    return x + y
```

```python
>>> add(1, 1)
2

>>> add(1.0, 1.0)
2.0

>>> try: add(1, 1.0)
... except Exception as e: print(f"{type(e).__name__}: {e}")
NotFoundLookupError: `add(1, 1.0)` could not be resolved.
Closest candidates are the following:
    add(x: int, y: int)
        <function add at ...> @ ...
    add(x: float, y: float)
        <function add at ...> @ ...
```
