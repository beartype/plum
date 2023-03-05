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

You can use `@dispatch` with other decorators without any problem:

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

>>> a.name = 1    # Not OK
NotFoundLookupError: For function `name` of `__main__.MyClass`, `(<__main__.MyClass object at 0x7f8cb8813eb0>, 1)` could not be resolved.
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
