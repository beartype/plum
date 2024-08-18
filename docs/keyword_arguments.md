# Keyword Arguments

````{important}
Before anything else, one thing must be stated very clearly:
dispatch, as implemented by Plum, is based on the _positional_ arguments to a function.
Keyword arguments are certainly supported, but they are not used in the decision making
for which method to call.
In particular, this means that _positional arguments without a default value must
always be given as positional arguments_!

Example:

```python
from plum import dispatch


@dispatch
def f(x: int):
    return x
```

```python
>>> f(1)    # OK
1

>>> try: f(x=1)  # Not OK
... except Exception as e: print(f"{type(e).__name__}: {e}")
NotFoundLookupError: `f()` could not be resolved...
```

See [below](why) for why this is the case.
````

## Default Arguments

Default arguments can be used.
The type annotation must match the default value otherwise an error is thrown.
As the example below illustrates, different default values can be used for
different methods:

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
def g(x, *, option="a"):
    return option
```

```python
>>> g(1)
'a'

>>> g(1, option="b")
'b'

>>> try: g(1, "b")  # This will not work, because `option` must be given as a keyword.
... except Exception as e: print(f"{type(e).__name__}: {e}")
NotFoundLookupError: `g(1, 'b')` could not be resolved...
```

(why)=
## Why Doesn't Dispatch Fully Support Keyword Arguments?

It would technically be possible to dispatch of keyword arguments.
Whereas Plum should or not is an ongoing discussion.

The main argument against is that dispatching on keyword arguments
would make the dispatch process sensitive to argument names.
For this to work well, the arguments of all methods of a function would
have to be named consistently.
This can be problematic if the methods of a function are spread across
multiple packages with different authors and code conventions.
In contrast, dispatching only on positional arguments means that
dispatch does not depend on argument names.

In general, Plum attempts to mimics how multiple dispatch works in the
[Julia programming language](https://docs.julialang.org/en/).

## I Really Want Keyword Arguments!

You can use the following pattern as a work-around,
which converts all arguments to positional arguments using a wrapper function:

```python
from plum import dispatch


def f(x=None, y=None):
    return _f(x, y)


@dispatch
def _f(x: int, y: None):
    print("Only `x` is provided! It is an integer.")


@dispatch
def _f(x: float, y: None):
    print("Only `x` is provided! It is a float.")


@dispatch
def _f(x: None, y: float):
    print("Only `y` is provided! It is a float.")


@dispatch
def _f(x: int, y: float):
    print("Both are provided!")
```

```python
>>> f(x=1)
Only `x` is provided! It is an integer.

>>> f(x=1.0)
Only `x` is provided! It is a float.

>>> try: f(y=1)
... except Exception as e: print(f"{type(e).__name__}: {e}")
NotFoundLookupError: `_f(None, 1)` could not be resolved...

>>> f(y=1.0)
Only `y` is provided! It is a float.

>>> f(x=1, y=1.0)
Both are provided!
```
