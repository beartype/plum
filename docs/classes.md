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


## Decorators

You can use `@dispatch` together with other decorators, provided the decorators are ordered correctly.
When combining `@dispatch` with other decorators (for example, `@staticmethod`, `@classmethod`, or `@property`), `@dispatch` must be the **inner** decorator (i.e., closest to the function definition) for dispatch to work correctly:

```python
from plum import dispatch


class MyClass:
    def __init__(self):
        self._name = None

    @property
    def name(self):
        return self._name

    @name.setter
    @dispatch
    def name(self, value: str):
        self._name = value
```

```python
>>> a = MyClass()

>>> a.name = "1"  # OK

>>> a.name = 1    # Not OK  # doctest:+SKIP
NotFoundLookupError: For function `name` of `__main__.MyClass`, `(<__main__.MyClass object at 0x7f8cb8813eb0>, 1)` could not be resolved.
```

For example, when using `@staticmethod`, `@dispatch` should be the inner decorator (i.e., `@dispatch` wraps the function first):

```python
from plum import dispatch


class MyClass:
    @staticmethod
    @dispatch
    def my_func(a: int, b: int) -> int:
        return a + b

    @staticmethod
    @dispatch
    def my_func(a: float, b: float) -> float:
        return a + b
```

```python
>>> MyClass.my_func(1, 2)
3

>>> MyClass.my_func(1.0, 2.0)
3.0
```


(forward-references)=
## Forward References

Imagine the following design:

```python
from plum import dispatch


class Real:
    @dispatch
    def __add__(self, other: Real):
        ...
```

If we try to run this, we get the following error:

% skip: next

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
      6         ...

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
        ...
```
