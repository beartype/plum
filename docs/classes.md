# Classes

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

## `@staticmethod`, `@classmethod`, and `@property.setter`

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

(forward-references)=
## Forward References

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
