(conversion-promotion)=
# Conversion and Promotion

## Return Types

When a return type is not matched, Plum will attempt to convert the result to the 
right type.

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
TypeError: Cannot convert `1` to `int`.
```

Plum will usually not know how to perform this conversion.
You can tell Plum how the conversion should be done with `add_conversion_method`:

```python
>>> add_conversion_method(type_from=str, type_to=int, f=int)

>>> f("1")
1
```

## Conversion With `convert`

The function `convert` can be used to convert objects of one type to another.
This is also what is used to perform the conversion in the case the return type
does not match.

Example:


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
TypeError: Cannot convert `<__main__.Rational object at 0x7f88f8369310>` to `numbers.Number`.
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

As above, instead of the decorator `conversion_method`, one can also use
`add_conversion_method`:


```python
>>> from plum import add_conversion_method

>>> add_conversion_method(type_from, type_to, conversion_function)
```

## Promotion

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
TypeError: No promotion rule for `int` and `float`.
```

You can add promotion rules with `add_promotion_rule`:

```python
>>> add_promotion_rule(int, float, float)

>>> add(1, 2.0)
TypeError: Cannot convert `1` to `float`.

>>> add_conversion_method(type_from=int, type_to=float, f=float)

>>> add(1, 2.0)
3.0
```
