(parametric)=
# Parametric Classes

## Construction

The decorator `@parametric` can be used to create parametric classes:

```python
from plum import dispatch, parametric


@parametric
class A:
    def __init__(self, x):
        self.x = x
```

You can create a version of `A` with a type parameter using `__getindex__`:

```python
>>> A
<class 'A'>

>>> A[int]
<class 'A[int]'>
```

These types `A[int]` can be regarded as subclasses of `A`:

```python
>>> issubclass(A[int], A)
True
```

We call `A[int]` a _concrete_ parametric type.
It is concrete because `A[int]` can be instantiated into an object:

```python
>>> A[int](1)
<A[int] object at ...>
```

When you don't instantiate a concrete parametric type, but try to instantiate `A`
directly, the type parameter is automatically inferred from the argument:

```python
>>> A(1)
<A[int] object at ...>

>>> A("1")
<A[str] object at ...>

>>> A(1.0)
 <A[float] object at ...>
```

You can use parametric types to perform dispatch:

```python
@dispatch
def f(x: A):
    return "Just some A"
    
    
@dispatch
def f(x: A[int]):
    return "A has an integer!"
    
    
@dispatch
def f(x: A[float]):
    return "A has a float!"
```

Note that parametric types are *covariant*, which means
that `A[T1]` is a subtype of `A[T2]` whenever `T1` is a subtype of `T2`:

```python
>>> from numbers import Number

>>> issubclass(A[int], A[Number])
True
```

For a concrete parametric type or an instance of a concrete parametric type, you
can extract the type parameter with `type_parameter`:

```python
>>> from plum import type_parameter

>>> type_parameter(A[int])
<class 'int'>

>>> type_parameter(A[int](1))
<class 'int'>
```

## Customisation

You can customise precisely how type parameters are inferred and instantiated
by overriding certain `@classmethod`s:

| Class Method | What does it do? |
| - | - |
| `__init_type_parameter__` | Initialise the type parameter. |
| `__infer_type_parameter__` | Infer the type parameter from the arguments. |
| `__le_type_parameter__` | For a given `left` and `right`, check whether `Type[left]` is a subtype of `Type[Right]`. |

How these methods work is best described with an example.
See also `help(parametric)` for information.

```python
from plum import dispatch, parametric, type_parameter


@parametric
class NTuple:
    def __init__(self, *args):
        # Check that the arguments satisfy the type specification.
        n, t = type_parameter(self)
        if len(args) != n or any(not isinstance(arg, t) for arg in args):
            raise ValueError("Incorrect arguments!")

        self.args = args

    @classmethod
    @dispatch
    def __init_type_parameter__(self, n: int, t: type):
        """Check whether the type parameters are valid."""
        # In this case, we use `@dispatch` to check the validity of the type parameter.
        return n, t

    @classmethod
    def __infer_type_parameter__(self, *args):
        """Inter the type parameter from the arguments."""
        n = len(args)
        # For simplicity, take the type of the first argument! We could do something
        # more refined here.
        t = type(args[0])  
        return n, t

    @classmethod
    def __le_type_parameter__(self, left, right):
        """Is `NTuple[left]` a subtype of `NTuple[right]`?"""
        n_left, t_left = left
        n_right, t_right = right
        return n_left == n_right and issubclass(t_left, t_right)
```

`NTuple` automatically infers an appropriate type parameter with
`__infer_type_parameter__`:

```python
>>> NTuple(10, 11, 12)
<NTuple[3, int] object at ...>
```

It also validates any given type parameter using `__init_type_parameter__`:

```python
>>> NTuple[2, int]     # OK
<class 'NTuple[2, int]'>

>>> try: NTuple[2, "int"]   # Not OK
... except Exception as e: print(f"{type(e).__name__}: {e}")
NotFoundLookupError: `NTuple.__init_type_parameter__(<class 'NTuple'>, 2, 'int')` could not be  resolved...

>>> try: NTuple[None, int]  # Also not OK
... except Exception as e: print(f"{type(e).__name__}: {e}")
NotFoundLookupError: `NTuple.__init_type_parameter__(<class 'NTuple'>, None, <class 'int'>)` could not be resolved...
```

Given a valid type parameter, it validates the arguments:

```python
>>> NTuple[2, int](10, 11)
<NTuple[2, int] object at ...>

>>> try: NTuple[2, int](10, 11, 12)
... except Exception as e: print(f"{type(e).__name__}: {e}")
ValueError: Incorrect arguments!

>>> try: NTuple[2, int](10, "11")
... except Exception as e: print(f"{type(e).__name__}: {e}")
ValueError: Incorrect arguments!
```

Finally, it implements the desired covariance:

```python
>>> from numbers import Number

>>> issubclass(NTuple[2, int], NTuple[2, Number])
True

>>> issubclass(NTuple[2, int], NTuple[2, float]) 
False

>>> issubclass(NTuple[2, int], NTuple[3, int]) 
False
```

## `Kind`
Plum provides a convience parametric class `Kind` which you can use to quickly
make a parametric wrapper object:

```python
>>> from plum import Kind

>>> this = Kind["This"](1)

>>> this
<plum.parametric.Kind['This'] object at ...>

>>> this.get()
1

>>> that = Kind["That"]("some", "args", "here")

>>> that
<plum.parametric.Kind['That'] object at ...>

>>> that.get()
('some', 'args', 'here')
```

For example, you can use this in the following way:

```python
from plum import dispatch


@dispatch
def i_expect_this(this: Kind["this"]):
    arg = this.get()
    ...


@dispatch
def i_expect_that(that: Kind["that"]):
    arg0, arg1, arg2 = that.get()
    ...
```

## `Val`

Plum provides a parametric class `Val` which you can use to bring information
from the object domain to the type domain.

Example:

```python
from plum import dispatch, Val


@dispatch
def algorithm(setting: Val["fast"], x):
    return "Running fast!"


@dispatch
def algorithm(setting: Val["slow"], x):
    return "Running slowly..."
```

```python
>>> algorithm(Val("fast"), 1)
'Running fast!'

>>> algorithm(Val("slow"), 1)
'Running slowly...'
```

`typing.Literal` fills a very similar purpose.
We recommend using `typing.Literal` instead.
`Val` is only useful for Python versions that do not have `typing.Literal`.
Those are Python 3.7 and below, but Plum does not support those versions.


## Example: `NDArray`
See [here](comparison-parametric).

