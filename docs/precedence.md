(method-precedence)=
# Method Precedence

The keyword argument `precedence` can be set to an integer value to specify
precedence levels of methods, which are used to break ambiguity.
Method precendence is a powerful tool that can be used to simplify more complicated designs.

Example:

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
AmbiguousLookupError: For function `mul_no_precedence`, `(<__main__.ZeroElement object at 0x7feb80140d00>, <__main__.SpecialisedElement object at 0x7feb605abfd0>)` is ambiguous among the following:
  Signature(__main__.ZeroElement, __main__.Element, implementation=<function mul_no_precedence at 0x7feb6066a700>) (precedence: 0)
  Signature(__main__.Element, __main__.SpecialisedElement, implementation=<function mul_no_precedence at 0x7feb3000f670>) (precedence: 0)

>>> mul(zero, specialised_element)
'zero'
```
