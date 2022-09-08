# Advanced Usage

## Abstract Function Definitions

A function can be abstractly defined using `dispatch.abstract`.
When a function is abstractly defined, the function is created, but no methods
are defined.

```python
from plum import dispatch

@dispatch.abstract
def f(x):
    pass
```

```python
>>> f
<function <function f at 0x7f9f6820aea0> with 0 method(s)>

>>> @dispatch
... def f(x: int):
...     pass

>>> f
<function <function f at 0x7f9f6820aea0> with 1 method(s)>
```

(method-precedence)=
## Method Precedence

The keyword argument `precedence` can be set to an integer value to specify
precedence levels of methods, which are used to break ambiguity:

```python
from plum import dispatch

class Element:
    pass


class ZeroElement(Element):
    pass


class SpecialisedElement(Element):
    pass


@dispatch
def mul_no_precedence(a: ZeroElement, b: Element):
    return "zero"


@dispatch
def mul_no_precedence(a: Element, b: SpecialisedElement):
    return "specialised operation"
    

@dispatch(precedence=1)
def mul(a: ZeroElement, b: Element):
    return "zero"


@dispatch
def mul(a: Element, b: SpecialisedElement):
    return "specialised operation"
```

```python
>>> zero = ZeroElement()

>>> specialised_element = SpecialisedElement()

>>> element = Element()

>>> mul(zero, element)
'zero'

>>> mul(element, specialised_element)
'specialised operation'

>>> mul_no_precedence(zero, specialised_element)
AmbiguousLookupError: For function "mul_no_precedence", signature Signature(__main__.ZeroElement, __main__.SpecialisedElement) is ambiguous among the following:
  Signature(__main__.ZeroElement, __main__.Element) (precedence: 0)
  Signature(__main__.Element, __main__.SpecialisedElement) (precedence: 0)

>>> mul(zero, specialised_element)
'zero'
```

The method precedences of all implementations of a function can be obtained
with the attribute `precedences`:

```python
>>> mul_no_precedence.precedences
{Signature(__main__.ZeroElement, __main__.Element): 0,
 Signature(__main__.Element, __main__.SpecialisedElement): 0}

>>> mul.precedences
{Signature(__main__.ZeroElement, __main__.Element): 1,
 Signature(__main__.Element, __main__.SpecialisedElement): 0}
```

## Parametric Classes

The decorator `@parametric` can be used to create parametric classes:

```python
from plum import dispatch, parametric

@parametric
class A:
    def __init__(self, x, *, y = 3):
        self.x = x
        self.y = y
    
    
@dispatch
def f(x: A):
    return "fallback: x={}".format(x.x)
    
    
@dispatch
def f(x: A[int]):
    return "int x={}".format(x.x)
    
    
@dispatch
def f(x: A[float]):
    return "float x={}".format(x.x)
```

```python
>>> A
__main__.A

>>> A[int]
__main__.A[builtins.int]

>>> issubclass(A[int], A)
True

>>> type(A(1)) == A[int]
True

>>> A[int](1)
<__main__.A[builtins.int] at 0x10c2bab70>

>>> f(A[int](1))
'int x=1'

>>> f(A(1))
'int x=1'

>>> f(A(1.0))
'float x=1.0'

>>> f(A(1 + 1j))
'fallback: x=1+1j'
```

**Note:** Calling `A[pars]` on parametrized type `A` instantiates the concrete
type with parameters `pars`.
If `A(args)` is called directly, the concrete type is first instantiated by
taking the type of all positional arguments, and then an instance of the type
is created.

This behaviour can be customized by overriding the `@classmethod`
`__infer_type_parameter__` of the parametric class.
This method must return the type parameter or a tuple of type parameters.

```python
from plum import parametric

@parametric
class NTuple:
    @classmethod
    def __infer_type_parameter__(self, *args):
        # Mimicks the type parameters of an `NTuple`.
        T = type(args[0])
        N = len(args)
        return (N, T)

    def __init__(self, *args):
        # Check that the arguments satisfy the type specification.
        T = type(self)._type_parameter[1]
        assert all(isinstance(val, T) for val in args)
        self.args = args
```

```python
>>> type(NTuple(1, 2, 3))
__main__.NTuple[3, <class 'int'>]
```

## Hooking Into Type Inference

With parametric classes, you can hook into Plum's type inference system to do cool
things!
Here's an example which introduces types for NumPy arrays of particular ranks:

```python
import numpy as np
from plum import dispatch, parametric, type_of


@parametric(runtime_type_of=True)
class NPArray(np.ndarray):
    """A type for NumPy arrays where the type parameter specifies the number of
    dimensions."""


@type_of.dispatch
def type_of(x: np.ndarray):
    # Hook into Plum's type inference system to produce an appropriate instance of
    # `NPArray` for NumPy arrays.
    return NPArray[x.ndim]


@dispatch
def f(x: NPArray[1]):
    return "vector"


@dispatch
def f(x: NPArray[2]):
    return "matrix"
```

```python
>>> f(np.random.randn(10))
'vector'

>>> f(np.random.randn(10, 10))
'matrix'

>>> f(np.random.randn(10, 10, 10))
NotFoundLookupError: For function "f", signature Signature(__main__.NPArray[3]) could not be resolved.
```

## Add Multiple Methods

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

>>> add(1, 1.0)
NotFoundLookupError: For function "add", signature Signature(builtins.int, builtins.float) could not be resolved.
```

## Extend a Function From Another Package

`Function.dispatch` can be used to extend a particular function from an external
package:

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

## Support for IPython Autoreload

Plum does not work out of the box with
[IPython's autoreload extension](https://ipython.readthedocs.io/en/stable/config/extensions/autoreload.html),
and if you reload a file where a class is defined, you will most likely break your dispatch table.

However, experimental support for IPython's autoreload is included into Plum,
but it is not enabled by default, as it overrides some internal methods of IPython.
To activate it, either set the environment variable `PLUM_AUTORELOAD=1` **before** loading plum

```bash
export PLUM_AUTORELOAD=1
```

or manually call the `autoreload.activate` method in an interactive session.

```python
import plum

plum.autoreload.activate()
```

If there are issues with autoreload, please open a bug report.
