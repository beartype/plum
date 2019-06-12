# [Plum: Multiple Dispatch in Python](https://github.com/wesselb/plum)

[![Build](https://travis-ci.org/wesselb/plum.svg?branch=master)](https://travis-ci.org/wesselb/plum)
[![Coverage Status](https://coveralls.io/repos/github/wesselb/plum/badge.svg?branch=master&service=github)](https://coveralls.io/github/wesselb/plum?branch=master)
[![Latest Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://wesselb.github.io/plum)

Everybody likes multiple dispatch, just like everybody likes plums.

* [Installation](#installation)
* [Basic Usage](#basic-usage)
* [Advanced Features by Example](#advanced-features-by-example)
    - [Dispatch From Type Annotations](#dispatch-from-type-annotations)
    - [Union Types](#union-types)
    - [Parametric Types](#parametric-types)
    - [Variable Arguments](#variable-arguments)
    - [Return Types](#return-types)
    - [Inheritance](#inheritance)
    - [Conversion](#conversion)
    - [Promotion](#promotion)
    - [Method Precedence](#method-precedence)
    - [Parametric Classes](#parametric-classes)
    - [Add Multiple Methods](#add-multiple-methods)
    - [Extend a Function From Another Package](#extend-a-function-from-another-package)
    - [Directly Invoke a Method](#directly-invoke-a-method)

## Installation

```
pip install plum-dispatch
```

## Basic Usage

Multiple dispatch allows you to implement multiple *methods* for the same 
*function*, where the methods specify the types of their arguments:

```python
from plum import dispatch

@dispatch(str)
def f(x):
    return 'This is a string!'
    

@dispatch(int)
def f(x):
    return 'This is an integer!'
```

```python
>>> f('1')
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


@dispatch(Number)
def f(x):
    return 'This is a number!'
```

Since a `float` is a `Number`, `f(1.0)` will return `'This is a number!'`.
But an `int` is also a `Number`, so `f(1)` can either return 
`'This is an integer!'` or `'This is a number!'`.
The rule of multiple dispatch is that the *most specific* method is chosen:


```python
>>> f(1)
'This is an integer!'
```

since an `int` is a `Number`, but a `Number` is not necessarily an `int`.

For an excellent and way more detailed overview of multiple dispatch, see the
[manual of the Julia Language](https://docs.julialang.org/en/).

## Features by Example

### Dispatch From Type Annotations

`Dispatcher.annotations` is an experimental feature that can be used to 
dispatch on a function's type annotations:

```python
from plum import dispatch, add_conversion_method

add_conversion_method(type_from=int, type_to=str, f=str)


@dispatch.annotations()
def int_to_str(x: int) -> str:
    return x
    
    
@dispatch.annotations()
def int_to_str(x):
    raise ValueError('I only take integers!')
```

```python
>>> int_to_str(1.0)
ValueError: I only take integers!

>>> int_to_str(1)
'1'
```

### Union Types

Sets can be used to instantiate union types:

```python
from plum import dispatch

@dispatch(object)
def f(x):
    print('fallback')


@dispatch({int, str})
def f(x):
    print('int or str')
```

```
>>> f(1)
int or str

>>> f('1')
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
from plum import dispatch, Tuple, List

@dispatch({tuple, list})
def f(x):
    print('tuple or list')
    
    
@dispatch(Tuple(int))
def f(x):
    print('tuple of int')
    
    
@dispatch(List(int))
def f(x):
    print('list of int')
```

```python
>>> f([1, 2])
'list of int'

>>> f([1, '2'])
'tuple or list'

>>> f((1, 2))
'tuple of int'

>>> f((1, '2'))
'tuple or list'
```

### Variable Arguments

A list can be used to specify variable arguments:

```python
from plum import dispatch

@dispatch(int)
def f(x):
    print('single argument')
    

@dispatch(int, [int])
def f(x, *xs):
    print('multiple arguments')
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

The keyword argument `return_type` can be set to specify return types:

```python
from plum import dispatch, add_conversion_method

@dispatch({int, str}, return_type=int)
def f(x):
    return x
```

```python
>>> f(1)
1

>>> f('1')
TypeError: Expected return type "builtins.int", but got type "builtins.str".

>>> add_conversion_method(type_from=str, type_to=int, f=int)

>>> f('1')
1

```

### Inheritance

Since every class in Python can be subclassed, diagonal dispatch cannot be 
implemented.
However, inheritance can be used to achieve a form of diagonal dispatch:

```python
from plum import Dispatcher, Referentiable, Self

class Real(Referentiable):
    dispatch = Dispatcher(in_class=Self)

    @dispatch(Self)
    def __add__(self, other):
        return 'real'
        

class Rational(Real, Referentiable):
    dispatch = Dispatcher(in_class=Self)

    @dispatch(Self)
    def __add__(self, other):
        return 'rational'
        

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


class Rational(object):
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

@dispatch(object, object)
def add(x, y):
    return add(*promote(x, y))
    
    
@dispatch(int, int)
def add(x, y):
    return x + y
    
    
@dispatch(float, float)
def add(x, y):
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

class Element(object):
    pass


class ZeroElement(Element):
    pass


class SpecialisedElement(Element):
    pass


@dispatch(ZeroElement, Element)
def mul_no_precedence(a, b):
    return 'zero'


@dispatch(Element, SpecialisedElement)
def mul_no_precedence(a, b):
    return 'specialised operation'
    

@dispatch(ZeroElement, Element, precedence=1)
def mul(a, b):
    return 'zero'


@dispatch(Element, SpecialisedElement)
def mul(a, b):
    return 'specialised operation'
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
class A(object):  # Must be a new-style class!
    pass
    
    
@dispatch(A)
def f(x):
    return 'fallback'
    
    
@dispatch(A(1))
def f(x):
    return '1'
    
    
@dispatch(A(2))
def f(x):
    return '2'
```

```python
>>> A
__main__.A

>>> A(1)
__main__.A{1}

>>> issubclass(A(1), A)
True

>>> A(1)()
<__main__.A{1} at 0x10c2bab70>

>>> f(A(1)())
'1'

>>> f(A(2)())
'2'

>>> f(A(3)())
'fallback'
```

### Add Multiple Methods

`Dispatcher.multi` can be used to implement multiple methods at once:

```python
from plum import dispatch

@dispatch.multi((int, int), (float, float))
def add(x, y):
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

@f.extend(int)
def f(x):
    return 'new behaviour'
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

@dispatch(int)
def f(x):
    return 'int'
    
    
@dispatch(str)
def f(x):
    return 'str'
```

```python
>>> f(1)
'int'

>>> f('1')
'str'

>>> f.invoke(int)('1')
'int'

>>> f.invoke(str)(1)
'str'
```
