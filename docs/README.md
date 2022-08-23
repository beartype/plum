# [Plum: Multiple Dispatch in Python](https://github.com/wesselb/plum)

[![DOI](https://zenodo.org/badge/110279931.svg)](https://zenodo.org/badge/latestdoi/110279931)
[![CI](https://github.com/wesselb/plum/workflows/CI/badge.svg?branch=master)](https://github.com/wesselb/plum/actions?query=workflow%3ACI)
[![Coverage Status](https://coveralls.io/repos/github/wesselb/plum/badge.svg?branch=master&service=github)](https://coveralls.io/github/wesselb/plum?branch=master)
[![Latest Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://wesselb.github.io/plum)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Everybody likes multiple dispatch, just like everybody likes plums.

 * [Installation](#installation)
 * [Basic Usage](#basic-usage)
 * [Scope of Functions](#scope-of-functions)
 * [Classes](#classes)
    - [`@staticmethod`, `@classmethod`, and `@property.setter`](#staticmethod-classmethod-and-propertysetter)
    - [Forward References](#forward-references)
 * [Keyword Arguments and Default Values](#keyword-arguments-and-default-values)
 * [Comparison with `multipledispatch`](#comparison-with-multipledispatch)
 * [Type System](#type-system)
    - [Union Types](#union-types)
    - [Parametric Types](#parametric-types)
    - [Variable Arguments](#variable-arguments)
    - [Return Types](#return-types)
 * [Conversion and Promotion](#conversion-and-promotion)
    - [Conversion](#conversion)
    - [Promotion](#promotion)
 * [Advanced Features](#advanced-features)
    - [Abstract Function Definitions](#abstract-function-definitions)
    - [Method Precedence](#method-precedence)
    - [Parametric Classes](#parametric-classes)
    - [Hooking Into Type Inference](#hooking-into-type-inference)
    - [Add Multiple Methods](#add-multiple-methods)
    - [Extend a Function From Another Package](#extend-a-function-from-another-package)
    - [Directly Invoke a Method](#directly-invoke-a-method)
 * [Support for IPython Autoreload](#support-for-ipython-autoreload)

## Installation

Plum requires Python 3.7 or higher.

```bash
pip install plum-dispatch
```

## Basic Usage

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
>>> f(1.0)
NotFoundLookupError: For function "f", signature Signature(builtins.float) could not be resolved.
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
{Signature(builtins.str): (<function __main__.f(x:str)>, builtins.object),
 Signature(builtins.int): (<function __main__.f(x:int)>, builtins.object),
 Signature(numbers.Number): (<function __main__.f(x:numbers.Number)>,
  builtins.object)}
```

In the values, the first element in the tuple is the implementation and the
second element the return type.

For an excellent and way more detailed overview of multiple dispatch, see the
[manual of the Julia Language](https://docs.julialang.org/en/).

## Scope of Functions

Consider the following package design.

**package/\_\_init\_\_.py**

```python
import a
import b
```

**package/a.py**

```python
from plum import dispatch

@dispatch
def f(x: int):
   return "int"
```

**package/b.py**

```python
from plum import dispatch

@dispatch
def f(x: float):
   return "float"
```

In a design like this, the methods for `f` recorded by `dispatch` are _global_:

```python
>>> from package.a import f

>>> f(1.0)
'float'
```

This could be what you want, but it can also be undesirable, because it means that 
someone could accidentally overwrite your methods.
To keep your functions private, you can create new dispatchers:

**package/\_\_init\_\_.py**

```python
import a
import b
```

**package/a.py**

```python
from plum import Dispatcher

dispatch = Dispatcher()


@dispatch
def f(x: int):
   return "int"
```

**package/b.py**

```python
from plum import Dispatcher

dispatch = Dispatcher()


@dispatch
def f(x: float):
   return "float"
```


```python
>>> from package.a import f

>>> f(1)
'int'

>>> f(1.0)
NotFoundLookupError: For function "f", signature Signature(builtins.float) could not be resolved.

>>> from package.b import f

>>> f(1)
NotFoundLookupError: For function "f", signature Signature(builtins.int) could not be resolved.

>>> f(1.0)
'float'
```


## Classes

You can use dispatch within classes:

```python
from plum import dispatch

class Real:
   @dispatch
   def __add__(self, other: int):
      return "int added"
   
   @dispatch
   def __add__(self, other: float):
      return "float added"
```

```python
>>> real = Real()

>>> real + 1
'int added'

>>> real + 1.0
'float added'
```

If you use other decorators, then `dispatch` must be the _outermost_ decorator:

```python
class Real:
   @dispatch
   @decorator
   def __add__(self, other: int):
      return "int added"
```

### `@staticmethod`, `@classmethod`, and `@property.setter`

In the case of `@staticmethod`, `@classmethod`, or `@property.setter`, the rules
are different:

1. The `@dispatch` decorator must be applied _before_ `@staticmethod`,
    `@classmethod`, and `@property.setter`. 
    This means that `@dispatch` is then _not_ the outermost decorator.   
2. The class must have _at least one_ other method where `@dispatch` is the
    outermost decorator.
    If this is not the case, you will need to add a dummy method, as the
    following example illustrates.

```python
from plum import dispatch

class MyClass:
    def __init__(self):
        self._name = None
       
    @property
    def property(self):
        return self._name

    @property.setter
    @dispatch
    def property(self, value: str):
        self._name = value
      
    @staticmethod
    @dispatch
    def f(x: int):
        return x

    @classmethod
    @dispatch
    def g(cls: type, x: float):
        return x

    @dispatch
    def _(self):
        # Dummy method that needs to be added whenever no method has
        # `@dispatch` as the outermost decorator.
        pass
```

If you don't add the dummy method whenever it is required, you will run into
a `ResolutionError`:

```python
from plum import dispatch

class MyClass:
    @staticmethod
    @dispatch
    def f(x: int):
        return x
```

```
>>> MyClass.f(1)
ResolutionError: Promise `Promise()` was not kept.
```

### Forward References

Imagine the following design:

```python
from plum import dispatch

class Real:
    @dispatch
    def __add__(self, other: Real):
        pass # Do something here. 
```

If we try to run this, we get the following error:

```python
NameError                                 Traceback (most recent call last)
<ipython-input-1-2c6fe56c8a98> in <module>
      1 from plum import dispatch
      2
----> 3 class Real:
      4     @dispatch
      5     def __add__(self, other: Real):

<ipython-input-1-2c6fe56c8a98> in Real()
      3 class Real:
      4     @dispatch
----> 5     def __add__(self, other: Real):
      6         pass # Do something here.

NameError: name 'Real' is not defined
```

The problem is that name `Real` is not yet defined, when `__add__` is defined and 
the type hint for `other` is set.
To circumvent this issue, you can use a forward reference:

```python
from plum import dispatch

class Real:
    @dispatch
    def __add__(self, other: "Real"):
        pass # Do something here. 
```

**Note:**
A forward reference `"A"` will resolve to the _next defined_ class `A` _in 
which dispatch is used_.
This works fine for self references.
In is recommended to only use forward references for self references.
For more advanced use cases of forward references, you can use `plum.type.PromisedType`.

## Keyword Arguments and Default Values

Default arguments can be used.
The type annotation must match the default value otherwise an error is thrown. 
As the example below illustrates, different default values can be used for different methods:

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
NotFoundLookupError: For function "f", signature Signature(builtins.int, builtins.str) could not be resolved.
```


## Comparison with `multipledispatch`

As an alternative to Plum, there is
[multipledispatch](https://github.com/mrocklin/multipledispatch), which also is a 
great solution.
Plum was developed to provide a slightly more featureful implementation of multiple 
dispatch.

#### Like `multipledispatch`, Plum's caching mechanism is optimised to minimise overhead.

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
 
#### Plum synergises with OOP.
Consider the following snippet:
   
```python
from multipledispatch import dispatch

class A:
    def f(self, x):
        return "fallback"
        

class B:
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

#### [Plum supports forward references.](#forward-references)

#### [Plum supports parametric types from `typing`.](#parametric-types)
   
#### Plum attempts to stay close to Julia's type system.
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

#### [Plum implements method precedence.](#method-precedence)
Method precedence can be a very powerful tool to simplify more complicated designs.

#### [Plum provides generic `convert` and `promote` functions.](#conversion-and-promotion)

## Type System

### Union Types

`typing.Union` can be used to instantiate union types:

```python
from typing import Union

from plum import dispatch

@dispatch
def f(x):
    return "fallback"


@dispatch
def f(x: Union[int, str]):
    return "int or str"
```

```python
>>> f(1)
'int or str'

>>> f("1")
'int or str'

>>> f(1.0)
'fallback'
```

### Parametric Types

The parametric types `typing.Tuple`, `typing.List`, `typing.Dict`,
`typing.Iterable`, and `typing.Sequence` can be used to dispatch on respectively
tuples, lists,  dictionaries, iterables, and sequence with particular types of
elements.
Importantly, the type system is *covariant*, as opposed to Julia's type 
system, which is *invariant*.

Example involving some parametric types:

```python
from typing import Union, Tuple, List, Dict

from plum import dispatch

@dispatch
def f(x: Union[tuple, list]):
    return "tuple or list"
    
    
@dispatch
def f(x: Tuple[int, int]):
    return "tuple of two ints"
    
    
@dispatch
def f(x: List[int]):
    return "list of int"


@dispatch
def f(x: Dict[int, str]):
   return "dict of int to str"
```

```python
>>> f([1, 2])
'list of int'

>>> f([1, "2"])
'tuple or list'

>>> f((1, 2))
'tuple of two ints'

>>> f((1, 2, 3))
'tuple or list'

>>> f((1, "2"))
'tuple or list'

>>> f({1: "2"})
'dict of int to str'
```

**Note:** Although parametric types are supported, parametric types do incur a 
significant  performance hit, because the type of every element in a list or tuple 
must be checked.
It is recommended to use parametric types only where absolutely necessary.

### Variable Arguments

A variable number of arguments can be used without any problem.

```python
from plum import dispatch

@dispatch
def f(x: int):
    return "single argument"
    

@dispatch
def f(x: int, *xs: int):
    return "multiple arguments"
```

```python
>>> f(1)
'single argument'

>>> f(1, 2)
'multiple arguments'

>>> f(1, 2, 3)
'multiple arguments'
```

### Return Types

Return types can be used without any problem.

```python
from typing import Union

from plum import dispatch, add_conversion_method

@dispatch
def f(x: Union[int, str]) -> int:
    return x
```

```python
>>> f(1)
1

>>> f("1")
TypeError: Cannot convert a "builtins.str" to a "builtins.int".

>>> add_conversion_method(type_from=str, type_to=int, f=int)

>>> f("1")
1

```

## Conversion and Promotion

### Conversion

The function `convert` can be used to convert objects of one type to another:

```python
from numbers import Number

from plum import convert


class Rational:
    def __init__(self, num, denom):
        self.num = num
        self.denom = denom
```

```python
>>> convert(0.5, Number)
0.5

>>> convert(Rational(1, 2), Number)
TypeError: Cannot convert a "__main__.Rational" to a "numbers.Number".
```

The `TypeError` indicates that `convert` does not know how to convert a 
`Rational` to a `Number`.
Let us implement that conversion:

```python
from operator import truediv

from plum import conversion_method
        

@conversion_method(type_from=Rational, type_to=Number)
def rational_to_number(q):
    return truediv(q.num, q.denom)
```

```python
>>> convert(Rational(1, 2), Number)
0.5
```

Instead of the decorator `conversion_method`, one can also use 
`add_conversion_method`:


```python
from plum import add_conversion_method

add_conversion_method(type_from, type_to, conversion_function)
```

### Promotion

The function `promote` can be used to promote objects to a common type:

```python
from plum import dispatch, promote, add_promotion_rule, add_conversion_method

@dispatch
def add(x, y):
    return add(*promote(x, y))
    
    
@dispatch
def add(x: int, y: int):
    return x + y
    
    
@dispatch
def add(x: float, y: float):
    return x + y
```

```python
>>> add(1, 2)
3

>>> add(1.0, 2.0)
3.0

>>> add(1, 2.0)
TypeError: No promotion rule for "builtins.int" and "builtins.float".

>>> add_promotion_rule(int, float, float)

>>> add(1, 2.0)
TypeError: Cannot convert a "builtins.int" to a "builtins.float".

>>> add_conversion_method(type_from=int, type_to=float, f=float)

>>> add(1, 2.0)
3.0
```

## Advanced Features

### Abstract Function Definitions

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

### Method Precedence

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

### Parametric Classes

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

### Hooking Into Type Inference

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

### Add Multiple Methods

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

### Extend a Function From Another Package

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

### Directly Invoke a Method

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

### Support for IPython Autoreload

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





