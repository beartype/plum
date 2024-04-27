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

>>> try: mul_no_precedence(zero, specialised_element)
... except Exception as e: print(f"{type(e).__name__}: {e}")
AmbiguousLookupError: `mul_no_precedence(<ZeroElement object at ...>, <SpecialisedElement
object at ...>)` is ambiguous.
Candidates:
    mul_no_precedence(a: ZeroElement, b: Element)
        <function mul_no_precedence at ...> @ ...md:26
    mul_no_precedence(a: Element, b: SpecialisedElement)
        <function mul_no_precedence at ...> @ ...

>>> mul(zero, specialised_element)
'zero'
```
