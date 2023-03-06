(union-aliases)=
# Union Aliases

To understand what union aliases are and what problem they solve, consider the
following example.
Suppose that we would want to implement a special addition function, and we would
want to implement it for all NumPy scalar types:

```python
import numpy as np

from typing import Union
from plum import dispatch


scalar_types = sum(np.sctypes.values(), [])  # All NumPy scalar types
Scalar = Union[tuple(scalar_types)]  # Union of all NumPy scalar types


@dispatch
def add(x: Scalar, y: Scalar):
    return x + y
```

This looks all fine, until you look at the documentation.
In particular, `help(add)` prints


```
Help on Function in module __main__:

add(x: Union[numpy.int8, numpy.int16, numpy.int32, numpy.int64, numpy.uint8, numpy.uint16, numpy.uint32, numpy.uint64, numpy.float16, numpy.float32, numpy.float64, numpy.float128, numpy.complex64, numpy.complex128, numpy.complex256, bool, object, bytes, str, numpy.void], y: Union[numpy.int8, numpy.int16, numpy.int32, numpy.int64, numpy.uint8, numpy.uint16, numpy.uint32, numpy.uint64, numpy.float16, numpy.float32, numpy.float64, numpy.float128, numpy.complex64, numpy.complex128, numpy.complex256, bool, object, bytes, str, numpy.void])
```

While the documentation is accurate, it is not at all helpful to expand the union in
its many elements, because it obscures the key message: `add(x, y)` is implemented
for all _scalars_.
A better option would be to print `add(x: Scalar, y: Scalar)`.
This is precisely what union aliases do:
by aliasing a union, you change the way it is displayed.
Union aliases must be activated explicitly, because the feature
monkeypatches `Union.__str__` and `Union.__repr__`.

```python
>>> from plum import activate_union_aliases, set_union_alias

>>> activate_union_aliases()

>>> set_union_alias(Scalar, alias="Scalar")
```

After this, `help(add)` now prints the following:

```python
Help on Function in module __main__:

add(x: Union[Scalar], y: Union[Scalar])
```

Hurray!
Note that the documentation prints `Union[Scalar]` rather than just `Scalar`.
This is intentional: it is to prevent breaking code that depends on how unions
print.
For example, printing just `Scalar` would omit the type parameter(s). 

Let's see with a few more examples how this works:

```python
>>> Scalar
typing.Union[Scalar]

>>> Union[tuple(scalar_types)]
typing.Union[Scalar]

>>> Union[tuple(scalar_types) + (tuple,)]       # Scalar or tuple
typing.Union[Scalar, tuple]

>>> Union[tuple(scalar_types) + (tuple, list)]  # Scalar or tuple or list
typing.Union[Scalar, tuple, list]
```

If we don't include all of `scalar_types`, we won't see `Scalar`, as desired:

```python
>>> Union[tuple(scalar_types[:-1])]
typing.Union[numpy.int8, numpy.int16, numpy.int32, numpy.int64, numpy.uint8, numpy.uint16, numpy.uint32, numpy.uint64, numpy.float16, numpy.float32, numpy.float64, numpy.float128, numpy.complex64, numpy.complex128, numpy.complex256, bool, object, bytes, str]
```

You can deactivate union aliases with `deactivate_union_aliases`:

```python
>>> from plum import deactivate_union_aliases

>>> deactivate_union_aliases()

>>> Scalar
typing.Union[numpy.int8, numpy.int16, numpy.int32, numpy.int64, numpy.uint8, numpy.uint16, numpy.uint32, numpy.uint64, numpy.float16, numpy.float32, numpy.float64, numpy.float128, numpy.complex64, numpy.complex128, numpy.complex256, bool, object, bytes, str, numpy.void]
```
