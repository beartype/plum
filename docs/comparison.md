# Comparison with `multipledispatch`

As an alternative to Plum, there is
[multipledispatch](https://github.com/mrocklin/multipledispatch), which also is a
great solution.
Plum was developed to provide a slightly more featureful implementation of multiple
dispatch.

**Like `multipledispatch`, Plum's caching mechanism is optimised to minimise overhead.**

```python
from multipledispatch import dispatch as dispatch_md
from plum import dispatch as dispatch_plum

@dispatch_md(int)
def f_md(x):
   return x


@dispatch_plum
def f_plum(x: int):
   return x


def f_native(x):
    return x
```

```python
>>> f_md(1); f_plum(1);  # Run once to populate cache.

>>> %timeit f_native(1)
82.4 ns ± 0.162 ns per loop (mean ± std. dev. of 7 runs, 10000000 loops each)

>>> %timeit f_md(1)
845 ns ± 77.1 ns per loop (mean ± std. dev. of 7 runs, 1000000 loops each)

>>> %timeit f_plum(1)
404 ns ± 2.83 ns per loop (mean ± std. dev. of 7 runs, 1000000 loops each)
```

*Plum synergises with OOP.*
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

This behaviour might be undesirable: since `B.f` isn't matched, we could want `A.f`
to be tried next.
Plum supports this:

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

[**Plum supports forward references.**](forward-references)

[**Plum supports parametric types from `typing`.**](parametric-types)

**Plum attempts to stay close to Julia's type system.**
For example, `multipledispatch`'s union type is not a true union type:

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

Plum does provide a true union type:

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

[**Plum implements method precedence.**](method-precedence)
Method precedence can be a very powerful tool to simplify more complicated designs.

[**Plum provides generic `convert` and `promote` functions.**](conversion-promotion)
