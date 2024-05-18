# Basic Usage

Multiple dispatch allows you to implement multiple *methods* for the same
*function*, where the methods specify the types of their arguments:

```python
from plum import dispatch


@dispatch
def f(x: str):
    return "This is a string!"


@dispatch
def f(x: int):
    return "This is an integer!"
```

```python
>>> f("1")
'This is a string!'

>>> f(1)
'This is an integer!'
```

We haven't implemented a method for `float`s, so in that case an exception
will be raised:

```python
>>> try: f(1.0)
... except Exception as e: print(f"{type(e).__name__}: {e}")
NotFoundLookupError: `f(1.0)` could not be resolved...
```

Instead of implementing a method for `float`s, let's implement a method for
all numbers:

```python
from numbers import Number


@dispatch
def f(x: Number):
    return "This is a number!"
```

Since a `float` is a `Number`, `f(1.0)` will return `"This is a number!"`.
But an `int` is also a `Number`, so `f(1)` can either return
`"This is an integer!"` or `"This is a number!"`.
The rule of multiple dispatch is that the *most specific* method is chosen:


```python
>>> f(1)
'This is an integer!'
```

since an `int` is a `Number`, but a `Number` is not necessarily an `int`.

For a function `f`, all available methods can be obtained with `f.methods`:

```python
>>> f.methods
List of 3 method(s):
    [0] f(x: str)
        <function f at ...> @ ...
    [1] f(x: int)
        <function f at ...> @ ...
    [2] f(x: numbers.Number)
        <function f at ...> @ ...
```

For an excellent and way more detailed overview of multiple dispatch, see the
[manual of the Julia Language](https://docs.julialang.org/en/).
