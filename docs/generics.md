# Custom Generic Types

Plum has **partial support** for dispatching on user-defined [generic classes](https://docs.python.org/3/library/typing.html#generics) — that is, classes you define yourself using `typing.Generic[T]`.  This page explains exactly what works, what doesn't, and the recommended pattern for writing fallback overloads.

```{note}
Built-in generic containers like `list[int]` and `dict[str, int]` are fully supported and inspected by Beartype directly.  This page is about *your own* generic classes such as `class Box(Generic[T])`.
```

## What works

Subscripted instances dispatch correctly:

```python
from typing import Any, Generic, TypeVar
from plum import dispatch

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


@dispatch
def unwrap(b: Box[int]) -> str:
    return "int box"


@dispatch
def unwrap(b: Box[str]) -> str:
    return "str box"
```

```python
>>> unwrap(Box[int](1))
'int box'

>>> unwrap(Box[str]("hello"))
'str box'
```

This works because Python sets `instance.__orig_class__ = Box[int]` after `Box[int](1)` finishes constructing the instance.  Plum reads that attribute during dispatch and uses Beartype's type-hint subtype ordering (`TypeHint(Box[int]) <= TypeHint(Box[str])`) to choose the most specific overload.

(generics-bare-instance-limitation)=
## The "bare instance" limitation

Python only sets `__orig_class__` when you instantiate through the subscripted form `Box[int](...)`.  When you write `Box(1)` directly there is **no** parameterization information attached to the instance — neither Plum nor Beartype can recover `T`.

This means a bare `Box(1)` cannot be told apart from `Box[anything](1)`.  To keep dispatch deterministic, Plum treats parameterized custom-generic hints as **non-matching** for instances that lack `__orig_class__`.  With only the two overloads above, calling `unwrap(Box(1))` raises `NotFoundLookupError`:

```python
>>> from plum import NotFoundLookupError
>>> try:
...     unwrap(Box(1))
... except NotFoundLookupError:
...     print("no match")
no match
```

## The `A[Any]` fallback pattern

The recommended way to handle bare instances is to register an explicit **`Any`-parameterized fallback overload**.  Extending the same `unwrap` above:

```python
@dispatch
def unwrap(b: Box[Any]) -> str:
    return "unknown parameterization"
```

Now all three call shapes resolve cleanly:

```python
>>> unwrap(Box(1))             # no __orig_class__ → falls through to Box[Any]
'unknown parameterization'

>>> unwrap(Box[int](1))        # __orig_class__ = Box[int]; most specific wins
'int box'

>>> unwrap(Box[str]("hello"))  # __orig_class__ = Box[str]; most specific wins
'str box'
```

`Box[Any]` is treated as a strict supertype of every other `Box[X]`, so:

- **Subscripted instances** still pick the most specific overload — `Box[int](1)` prefers `Box[int]` over `Box[Any]`.
- **Bare instances** match only `Box[Any]` (the other overloads are excluded because there is no parameterization to verify), so dispatch is unambiguous.

```{tip}
Think of `A[Any]` as the explicit way to say *"this overload is the fallback for any `A` instance whose parameter is unknown at runtime"*.  Without it, bare instances will raise `NotFoundLookupError` when only parameterized overloads are registered.
```

## Bare class hints (`Box` without brackets)

You can also write a fallback against the **bare** (unsubscripted) class:

% skip: start

```python
@dispatch
def g(b: Box) -> str:
    return "bare Box"


@dispatch
def g(b: Box[int]) -> str:
    return "int"
```

A bare hint like `Box` behaves the same way as `Box[Any]` for dispatch purposes — every `Box` instance matches it, and parameterized overloads still win for subscripted instances when their parameter agrees.  `Box` and `Box[Any]` are interchangeable as fallback overloads; pick whichever reads more clearly in your codebase.

% skip: end

## Why this isn't fully automatic

There are two fundamental limits at play:

1. **Python only attaches `__orig_class__` on subscripted construction.**  An instance created via `Box(1)` simply does not carry information about `T`, so no runtime introspection can recover it.
1. **Beartype validates type parameters by inspecting elements**, which works for containers (`list`, `dict`, etc.) but not for user-defined generic classes whose type-variable usage is opaque to the runtime.

Rather than guess or silently pick an arbitrary overload, Plum requires you to
state your intent explicitly via the `A[Any]` (or bare `A`) fallback overload.

## Summary

| Call                | Best overload chosen                                            |
| ------------------- | --------------------------------------------------------------- |
| `f(Box[int](1))`    | `Box[int]` (or `Box[Any]` / `Box` if `Box[int]` not present)    |
| `f(Box[str]("x"))`  | `Box[str]` (or `Box[Any]` / `Box` if `Box[str]` not present)    |
| `f(Box(1))`         | `Box[Any]` or bare `Box` only; `NotFoundLookupError` if absent  |

For more advanced parametric-class machinery (covariance, custom type-parameter inference, etc.), see [Parametric Classes](parametric).

(generics-performance)=
## Performance

Generic dispatch carries a small overhead compared to a regular faithful type.
The table below is generated each time the documentation is built so the numbers
reflect your actual hardware and Python version.

Two scenarios are measured:

- **Faithful** — only a bare `B` overload (no type-parameter overloads).  Plum
  uses the fast faithful-cache path.
- **Generic** — `A[Any]`, `A[int]`, and `A[str]` overloads.  Plum uses the
  two-tier generic cache, keyed on `__orig_class__` when present.

```{include} _generated/generics_timing.md
```

The faithful path is the fastest because Plum caches by `type(arg)` and checks
membership with a single `issubclass` call.  The generic path must additionally
read `__orig_class__` (or detect its absence), build the two-tier cache key, and
run the TypeHint subtype check on a cache miss.

```{tip}
If your code only dispatches on the *class* `A` and never needs to distinguish
`A[int]` from `A[str]`, declare a bare `A` (or `B` in the example above) overload
and omit the parameterized ones.  You get the faithful-cache speed with no change
to the calling code.
```
