# Support for IPython Autoreload

Plum does not work out of the box with
[IPython's autoreload extension](https://ipython.readthedocs.io/en/stable/config/extensions/autoreload.html),
and, if you reload a file where a class is defined,
you will most likely break your dispatch table.

Experimental support for IPython's autoreload is included into Plum,
but it is not enabled by default, as it overrides some internal methods of IPython.
To activate it, either set the environment variable `PLUM_AUTORELOAD=1` *before* loading plum

```bash
export PLUM_AUTORELOAD=1
```

or use `activate_autoreload`:

```python
>>> from plum import activate_autoreload

>>> activate_autoreload()
```

If there are issues with autoreload, please open an issue.

You can disable the feature with `deactivate_autoreload`:

```python
>>> from plum import deactivate_autoreload

>>> deactivate_autoreload()
```
