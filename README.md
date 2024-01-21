# [Plum: Multiple Dispatch in Python](https://github.com/beartype/plum)

[![DOI](https://zenodo.org/badge/110279931.svg)](https://zenodo.org/badge/latestdoi/110279931)
[![CI](https://github.com/beartype/plum/workflows/CI/badge.svg?branch=master)](https://github.com/beartype/plum/actions?query=workflow%3ACI)
[![Coverage Status](https://coveralls.io/repos/github/beartype/plum/badge.svg?branch=master&service=github)](https://coveralls.io/github/beartype/plum?branch=master)
[![Latest Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://beartype.github.io/plum)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Everybody likes multiple dispatch, just like everybody likes plums.

The design philosophy of Plum is to provide an implementation of multiple dispatch that is Pythonic, yet close to how [Julia](http://julialang.org/) does it.
[See here for a comparison between Plum, `multipledispatch`, and `multimethod`.](https://beartype.github.io/plum/comparison.html)

*Note:*
Plum 2 is now powered by [Beartype](https://github.com/beartype/beartype)!
If you notice any issues with the new release, please open an issue.

# Installation

Plum requires Python 3.8 or higher.

```bash
pip install plum-dispatch
```

# [Documentation](https://beartype.github.io/plum)

See [here](https://beartype.github.io/plum).

# What's This?

Plum brings your type annotations to life:

```python
from numbers import Number

from plum import dispatch


@dispatch
def f(x: str):
    return "This is a string!"


@dispatch
def f(x: int):
    return "This is an integer!"


@dispatch
def f(x: Number):
    return "This is a general number, but I don't know which type."
```

```python
>>> f("1")
'This is a string!'

>>> f(1)
'This is an integer!'

>>> f(1.0)
'This is a number, but I don't know which type.'

>>> f(object())
NotFoundLookupError: For function `f`, `(<object object at 0x7fb528458190>,)` could not be resolved.
```

This also works for multiple arguments, enabling some neat design patterns:

```python
from numbers import Number, Real, Rational

from plum import dispatch


@dispatch
def multiply(x: Number, y: Number):
    return "Performing fallback implementation of multiplication..."


@dispatch
def multiply(x: Real, y: Real):
    return "Performing specialised implementation for reals..."


@dispatch
def multiply(x: Rational, y: Rational):
    return "Performing specialised implementation for rationals..."
```

```python
>>> multiply(1, 1)
'Performing specialised implementation for rationals...'

>>> multiply(1.0, 1.0)
'Performing specialised implementation for reals...'

>>> multiply(1j, 1j)
'Performing fallback implementation of multiplication...'

>>> multiply(1, 1.0)  # For mixed types, it automatically chooses the right optimisation!
'Performing specialised implementation for reals...'
```
