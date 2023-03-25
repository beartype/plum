# Comparison with Other Multiple Dispatch Implementations

There are a few really great alternatives to Plum, most notably
[multipledispatch](https://github.com/mrocklin/multipledispatch)
and [multimethod](https://github.com/coady/multimethod).
Below we describe what sets Plum apart from other implementations.

## Powered by [Beartype](https://github.com/beartype/beartype)

The arguably most appealing aspect of Plum is that it is powered by
[Beartype](https://github.com/beartype/beartype),
which means that all the heavy lifting around correctly handling
type hints from `typing` is taken care of.
Getting this right is _very_ difficult,
and Plum has absolutely no intention to mess around with this;
Plum very gladly lets Beartype handle the difficult stuff.

## Design Goal: Mimic Julia's Type System

A central goal of Plum is to stay close to Julia's type system.
This is not necessarily the case for other packages.

For example,

```python
from multipledispatch import dispatch


@dispatch((object, int), int)
def f(x, y):
    return "first"
    

@dispatch(int, object)
def f(x, y):
    return "second"
```

```python
>>> f(1, 1)
'first'
```

Because the union of `object` and `int` is `object`, `f(1, 1)` should raise an
ambiguity error!
For example, compare with Julia:

```julia
julia> f(x::Union{Any, Int}, y::Int) = "first"
f (generic function with 1 method)

julia> f(x::Int, y::Any) = "second"
f (generic function with 2 methods)

julia> f(3, 3)
ERROR: MethodError: f(::Int64, ::Int64) is ambiguous. Candidates:
  f(x, y::Int64) in Main at REPL[1]:1
  f(x::Int64, y) in Main at REPL[2]:1
```

Plum handles this correctly.

```python
from typing import Union

from plum import dispatch


@dispatch
def f(x: Union[object, int], y: int):
    return "first"


@dispatch
def f(x: int, y: object):
    return "second"
```

```python
>>> f(1, 1)
AmbiguousLookupError: For function "f", signature Signature(builtins.int, builtins.int) is ambiguous among the following:
  Signature(builtins.object, builtins.int) (precedence: 0)
  Signature(builtins.int, builtins.object) (precedence: 0)
```

Just to sanity check that things are indeed working correctly:

```python
>>> f(1.0, 1)
'first'

>>> f(1, 1.0)
'second'
```

## Correct Handling of Default Values

Plum correctly handles default values.

For example,

```python
from multimethod import multimethod


@multimethod
def f(x: int, y: int = 1):
    return y
```

```python
>>> f(1, 1)  # OK
1

>>> f(1, 1.0)  # Not OK: no error is raised!
1.0
```

In comparison,

```python
from plum import dispatch


@dispatch
def f(x: int, y: int = 1):
    return y
```

```python
>>> f(1, 1)  # OK
1

>>> f(1, 1.0)  # OK: error is raised!
NotFoundLookupError: For function `f`, `(1, 1.0)` could not be resolved.
```


## Careful Synergy With OOP

Plum takes OOP very seriously.

Consider the following snippet:

```python
from multipledispatch import dispatch


class A:
    def f(self, x):
        return "fallback"
        

class B(A):
    @dispatch(int)
    def f(self, x):
        return x
```

```python
>>> b = B()

>>> b.f(1)
1

>>> b.f("1")
NotImplementedError: Could not find signature for f: <str>
```

Similarly,

```python
from multimethod import multimethod


class A:
    def f(self, x):
        return "fallback"
        

class B(A):
    @multimethod
    def f(self, x: int):
        return x
```

```python
>>> b = B()

>>> b.f(1)
1

>>> b.f("1")
DispatchError: ('f: 0 methods found', (<class '__main__.B'>, <class 'str'>), [])
```

This behaviour is undesirable.
Since `B.f` isn't matched, according to OOP principles, `A.f` should be tried next.
Plum correctly implements this:

```python
from plum import dispatch


class A:
    def f(self, x):
        return "fallback"


class B(A):
    @dispatch
    def f(self, x: int):
        return x
```

```python
>>> b = B()

>>> b.f(1)
1

>>> b.f("1")
'fallback'
```

(comparison-parametric)=
## Parametric Classes
Plum provides `@parametric`, which you can use to make your wildest parametric type
dreams come true.
For example, you can use it to dispatch on NumPy array shapes and sizes without
making concessions:

```python
from plum import dispatch, parametric
from typing import Any, Optional, Tuple, Union

import numpy as np


class NDArrayMeta(type):
    def __instancecheck__(self, x):
        if self.concrete:
            shape, dtype = self.type_parameter
        else:
            shape, dtype = None, None
        return (
            isinstance(x, np.ndarray)
            and (shape is None or x.shape == shape)
            and (dtype is None or x.dtype == dtype)
        )


@parametric
class NDArray(np.ndarray, metaclass=NDArrayMeta):
    @classmethod
    @dispatch
    def __init_type_parameter__(
        cls,
        shape: Optional[Tuple[int, ...]],
        dtype: Optional[Any],
    ):
        """Validate the type parameter."""
        return shape, dtype

    @classmethod
    @dispatch
    def __le_type_parameter__(
        cls,
        left: Tuple[Optional[Tuple[int, ...]], Optional[Any]],
        right: Tuple[Optional[Tuple[int, ...]], Optional[Any]],
    ):
        """Define an order on type parameters. That is, check whether
        `left <= right` or not."""
        shape_left, dtype_left = left
        shape_right, dtype_right = right
        return (
            (shape_right is None or shape_left == shape_right)
            and (dtype_right is None or dtype_left == dtype_right)
        )


@dispatch
def f(x: np.ndarray):
    print("Any NP array!")


@dispatch
def f(x: NDArray[(2, 2), None]):
    print("A 2x2 array!")


@dispatch
def f(x: NDArray[None, int]):
    print("An int array!")


@dispatch
def f(x: NDArray[(2, 2), int]):
    print("A 2x2 int array!")


f(np.ones((3, 3)))       # Any NP array!
f(np.ones((3, 3), int))  # An int array!
f(np.ones((2, 2)))       # A 2x2 array!
f(np.ones((2, 2), int))  # A 2x2 int array!
```

## Feature Rich
Plum implements numerous features nowhere else to be found:

* [method precedence](method-precedence),
    a powerful tool to simplify more complicated designs;
* [generic `convert` and `promote` functions](conversion-promotion);
* [specialised](moduletype) [types](promisedtype) for niche use cases;
* [union aliases](union-aliases); and
* more!
