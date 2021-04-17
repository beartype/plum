# [Plum: Multiple Dispatch in Python](https://github.com/wesselb/plum)

[![CI](https://github.com/wesselb/plum/workflows/CI/badge.svg?branch=master)](https://github.com/wesselb/plum/actions?query=workflow%3ACI)
[![Coverage Status](https://coveralls.io/repos/github/wesselb/plum/badge.svg?branch=master&service=github)](https://coveralls.io/github/wesselb/plum?branch=master)
[![Latest Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://wesselb.github.io/plum)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Everybody likes multiple dispatch, just like everybody likes plums.

_The current `master` is unreleased._

 * [Installation](#installation)
 * [Basic Usage](#basic-usage)
 * [Scope of Functions](#scope-of-functions)
 * [Classes](#classes)
    - [Forward References](#forward-references)
    - [Diagonal Dispatch](#diagonal-dispatch)
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
    - [Method Precedence](#method-precedence)
    - [Parametric Classes](#parametric-classes)
    - [Add Multiple Methods](#add-multiple-methods)
    - [Extend a Function From Another Package](#extend-a-function-from-another-package)
    - [Directly Invoke a Method](#directly-invoke-a-method)

## Installation

Plum requires Python 3.6 or higher.

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

This can be convenient, but it could also be undesirable, because it means that anyone 
can attach new behaviour to your functions.
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

If you use other decorators, then `dispatch` must be the _last_ decorator:

```python
class Real:
   @dispatch
   @decorator
   def __add__(self, other: int):
      return "int added"
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

#### Word of Caution

A forward reference `"A"` will resolve to the next class `A` that is defined _and in 
which dispatch is used_.
In particular, this works for self references.
In is recommended to only use forward references for self references.
For more advanced use cases of forward references, you can use `plum.type.PromisedType`.

### Diagonal Dispatch

Since every class in Python can be subclassed, diagonal dispatch cannot be
implemented.
However, inheritance can be used to achieve a form of diagonal dispatch:

```python
from plum import dispatch

class Real:
    @dispatch
    def __add__(self, other: "Real"):
        return "real"
        

class Rational(Real):
    @dispatch
    def __add__(self, other: "Rational"):
        return "rational"
        

real = Real()
rational = Rational()
```

```python
>>> real + real
'real'

>>> real + rational
'real'

>>> rational + real
'real'

>>> rational + rational
'rational'
```

## Keyword Arguments and Default Values

Keyword arguments can be used, but are *not* dispatched on.
As a convention, arguments with default values should always be called as keyword 
arguments.

Example:

```python
from plum import dispatch

@dispatch
def f(x, option="a"):
    return f"Value for option: {option}"
```

```python
>>> f(1)              # This is fine.
'Value for option: a'

>>> f(1, option="b")  # This is also fine.
'Value for option: b'

>>> f(1, "b")         # This will *not* work!
NotFoundLookupError: For function "f", signature Signature(builtins.int, builtins.str) could not be resolved.
```

If you want to use a default value for a positional argument, use the following pattern
instead:


```python
from plum import dispatch

@dispatch
def f(x, option):
    return f"Value for option: {option}"


@dispatch
def f(x):
    return f(x, "a")  # Use default value for `option`.
```

```python
>>> f(1)              # This is fine.
'Value for option: a'

>>> f(1, "b")         # And this will work!
'Value for option: b'

>>> f(1, option="b")  # But this won't.
TypeError: f() got an unexpected keyword argument 'option'
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

The parametric types `typing.Tuple` and `typing.List` can be used to dispatch on tuples 
and lists with particular types of elements.
Importantly, the type system is *covariant*, as opposed to Julia's type 
system, which is *invariant*.

```python
from typing import Union, Tuple, List

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

### Parametric Classes

The decorator `parametric` can be used to create parametric classes:

```python
from plum import dispatch, parametric

@parametric
class A:
    pass
    
    
@dispatch
def f(x: A):
    return "fallback"
    
    
@dispatch
def f(x: A[1]):
    return "1"
    
    
@dispatch
def f(x: A[2]):
    return "2"
```

```python
>>> A
__main__.A

>>> A[1]
__main__.A[1]

>>> issubclass(A[1], A)
True

>>> A[1]()
<__main__.A[1] at 0x10c2bab70>

>>> f(A[1]())
'1'

>>> f(A[2]())
'2'

>>> f(A[3]())
'fallback'
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
