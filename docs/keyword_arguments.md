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

>>> f(x=1)  # Not OK
NotFoundLookupError: For function `f`, `()` could not be resolved.
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
def f(x, *, option="a"):
    return option
```

```python
>>> f(1)
'a'

>>> f(1, option="b")
'b'

>>> f(1, "b")  # This will not work, because `option` must be given as a keyword.
NotFoundLookupError: For function `f`, `(1, 'b')` could not be resolved.
```

(why)=
## Why Doesn't Dispatch Fully Support Keyword Arguments?

That's a very good question, and unfortunately I don't have a strong answer.
The main reason is that it presents some new challenges.
Is not entirely clear how
this would work.
For example, consider the following scenario:

```python
@dispatch
def f(x: int, y: float):
    ... # Method 1


@dispatch
def f(y: float, x: int):
   ... # Method 2
```

Then calling `f(1, 1.0)` would call method 1 and calling `f(1.0, 1)` would call method 2.

What might be confusing is what `f(x=1.0, y=1)` would do.
For method 1, the call would be equivalent to `f(1.0, 1)`, which wouldn't match.
For method 2, the call would be equivalent to `f(1, 1.0)`, which also wouldn't match.
The strange thing is that the arguments are switched around between the two methods
because the names don't line up.

Perhaps this a poor example, but what's going wrong is the following.
In Python, there are two ways to say that a particular argument should have a value:

1. by _position_, or
2. by _name_.

Once you name things, the position becomes irrelevant.
And once you position an argument, the name of the argument as written in the function
doesn't matter.
Hence, in some sense, it's an either-or situation where you have to choose to
designate arguments by position _or_ designate arguments by name.

Currently, the whole multiple dispatch system has been designed around
arguments-designated-by-position (and type), which is, as argued above,
somehow incongruent with designating arguments by name.
Why?
Once you name things, the position becomes irrelevant;
and once you position something, the name of the argument becomes irrelevant.

Therefore, if we were to support naming arguments,
how precisely this would work would have to be spelled out in detail.
