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

In multiple dispatch, a function can have many implementations, called methods.
For all methods of a function, what is meant by the first argument is unambiguous and
clear.
However, what is meant by an argument named `x` depends on where a method
positioned `x`:
for some methods, `x` might be the first argument, whereas for other method `x`
might be the second argument.
In general, for a function with many methods, argument `x` does not have a unique
position.
In other words, for functions with many methods,
there is usually no correspondence between argument names and positions.

We therefore see that
supporting both positional and named arguments hence results in a specification that
mixes two non-corresponding systems.
Whereas this would be possible, and admittedly it would be convenient to support named
arguments, it would add substantial complexity to the dispatch process.
In addition, for named arguments to be usable,
it would require all methods of a function
to name their arguments in a consistent manner.
This can be particularly problematic if the methods of a function are spread across
multiple packages with different authors and code conventions.

In general, Plum closely mimics how multiple dispatch works in the
[Julia programming language](https://docs.julialang.org/en/).
