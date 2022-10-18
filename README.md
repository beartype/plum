# [Plum: Multiple Dispatch in Python](https://github.com/wesselb/plum)

[![DOI](https://zenodo.org/badge/110279931.svg)](https://zenodo.org/badge/latestdoi/110279931)
[![CI](https://github.com/wesselb/plum/workflows/CI/badge.svg?branch=master)](https://github.com/wesselb/plum/actions?query=workflow%3ACI)
[![Coverage Status](https://coveralls.io/repos/github/wesselb/plum/badge.svg?branch=master&service=github)](https://coveralls.io/github/wesselb/plum?branch=master)
[![Latest Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://wesselb.github.io/plum)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Everybody likes multiple dispatch, just like everybody likes plums.

# Installation

Plum requires Python 3.7 or higher.

```bash
pip install plum-dispatch
```

# [Documentation](https://wesselb.github.io/plum)

See [here](https://wesselb.github.io/plum).

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
"This is a number, but I don't know which type."

>>> f(object())
NotFoundLookupError: For function "f", signature Signature(builtins.object) could not be resolved.
```