# [Plum: Multiple Dispatch in Python](https://github.com/wesselb/plum)

[![CI](https://github.com/wesselb/plum/workflows/CI/badge.svg?branch=master)](https://github.com/wesselb/plum/actions?query=workflow%3ACI)
[![Coverage Status](https://coveralls.io/repos/github/wesselb/plum/badge.svg?branch=master&service=github)](https://coveralls.io/github/wesselb/plum?branch=master)
[![Latest Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://wesselb.github.io/plum)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Everybody likes multiple dispatch, just like everybody likes plums.

_The current `master` is unreleased._

* [Installation](#installation)
* [Basic Usage](#basic-usage)
* [Features by Example](#features-by-example)
    - [Dispatch From Type Annotations](#dispatch-from-type-annotations)
    - [Union Types](#union-types)
    - [Parametric Types](#parametric-types)
    - [Variable Arguments](#variable-arguments)
    - [Return Types](#return-types)
    - [Subclassing](#subclassing)
        + [Diagonal Dispatch](#diagonal-dispatch)
    - [Conversion](#conversion)
    - [Promotion](#promotion)
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
NotFoundLookupError: For function "f", signature (builtins.float) could not be resolved.
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

## Features by Example

### Union Types

Sets can be used to instantiate union types:

```python
from plum import dispatch

@dispatch
def f(x):
    print("fallback")


@dispatch
def f(x: {int, str}):
    print("int or str")
```

```
>>> f(1)
int or str

>>> f("1")
int or str

>>> f(1.0)
fallback
```

### Parametric Types

The parametric types `Tuple` and `List` can be used to dispatch on tuples 
and lists with particular types of elements.
Importantly, the type system is *covariant*, as opposed to Julia's type 
system, which is *invariant*.

```python
from typing import Tuple, List

from plum import dispatch

@dispatch
def f(x: {tuple, list}):
    print("tuple or list")
    
    
@dispatch
def f(x: Tuple[int, int]):
    print("tuple of two ints")
    
    
@dispatch
def f(x: List[int]):
    print("list of int")
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

### Variable Arguments

A variable number of arguments can be used without any problem.

```python
from plum import dispatch

@dispatch
def f(x: int):
    print("single argument")
    

@dispatch
def f(x: int, *xs: int):
    print("multiple arguments")
```

```
>>> f(1)
single argument

>>> f(1, 2)
multiple arguments

>>> f(1, 2, 3)
multiple arguments
```

### Return Types

Return types can be used without any problem.

```python
from plum import dispatch, add_conversion_method

@dispatch
def f(x: {int, str}) -> int:
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

### Subclassing

Imagine the following design:

```python
from plum import dispatch

class Real:
    @dispatch
    def __add__(self, other: Real):
        pass # Do something here. 
```

If we try to run this, we get the following error:

```
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

The problem is that, when `__add__` is defined and the type hint for `other` is set,
the name `Real` is not yet defined.
To circumvent this issue, Plum provides the metaclass `Referentiable` and type `Self`.
The proposed solution is to set the metaclass of `Real` to `Referentiable` and use
`Self` as a substitute for `Real`:

```python
from plum import Dispatcher, Referentiable, Self

class Real(metaclass=Referentiable):
    dispatch = Dispatcher(in_class=Self)
    
    @dispatch
    def __add__(self, other: Self):
        pass # Do something here. 
```

Note that you must create another `dispatch` inside the class, which will only be 
visible within the class.
If you are already using a metaclass, like `abc.ABCMeta`, then you can apply 
`Referentiable` as follows:

```python
import abc

from plum import Dispatcher, Referentiable, Self

class Real(metaclass=Referentiable(abc.ABCMeta)):
    dispatch = Dispatcher(in_class=Self)
    
    @dispatch
    def __add__(self, other: Self):
        pass # Do something here. 
```

Plum synergises with `abc`.

#### Diagonal Dispatch

Since every class in Python can be subclassed, diagonal dispatch cannot be 
implemented.
However, inheritance can be used to achieve a form of diagonal dispatch:

```python
from plum import Dispatcher, Referentiable, Self

class Real(metaclass=Referentiable):
    dispatch = Dispatcher(in_class=Self)

    @dispatch
    def __add__(self, other: Self):
        return "real"
        

class Rational(Real):
    dispatch = Dispatcher(in_class=Self)

    @dispatch
    def __add__(self, other: Self):
        return "rational"
        

real = Real()
rational = Rational()
```

```
>>> real + real
'real'

>>> real + rational
'real'

>>> rational + real
'real'

>>> rational + rational
'rational'
```

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
AmbiguousLookupError: For function "mul_no_precedence", signature (__main__.ZeroElement, __main__.SpecialisedElement) is ambiguous among the following:
  (__main__.ZeroElement, __main__.Element) (precedence: 0)
  (__main__.Element, __main__.SpecialisedElement) (precedence: 0)

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
from plum import dispatch

@dispatch.multi((int, int), (float, float))
def add(x: {int, float}, y: {int, float}):
    return x + y
```

```python
>>> add(1, 1)
2

>>> add(1.0, 1.0)
2.0

>>> add(1, 1.0)
NotFoundLookupError: For function "add", signature (builtins.int, builtins.float) could not be resolved.
```

### Extend a Function From Another Package

`Function.extend` can be used to extend a particular function:

```python
from package import f

@f.extend
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
