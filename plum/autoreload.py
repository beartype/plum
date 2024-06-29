import os

from .dispatcher import clear_all_cache
from .type import type_mapping

__all__ = ["activate_autoreload", "deactivate_autoreload"]


def _update_instances(old: type, new: type) -> None:
    """First call the original implementation of Autoreload's :meth:`update_instances`,
    and then use :obj:`.type._type_mapping` to map type `old` to the type `new`.

    Args:
        old (type): Old type.
        new (type): New type.
    """
    _update_instances_original(old, new)  # type: ignore[misc]

    type_mapping[old] = new

    # There might be an existing value in `_type_mapping` that should be replaced by
    # `new`. Resolve these chains.
    for k, v in type_mapping.items():
        while v in type_mapping:
            v = type_mapping[v]
        type_mapping[k] = v

    # Since types have changed, clear the cache of everything.
    clear_all_cache()


_update_instances_original = None
"""function: Original implementation of :func:`update_instances`."""


def activate_autoreload() -> None:
    """Pirate Autoreload's `update_instance` function to have Plum work with
    Autoreload."""
    from IPython.extensions import autoreload

    # First, cache the original method so we can deactivate ourselves.
    global _update_instances_original
    if _update_instances_original is None:
        _update_instances_original = autoreload.update_instances

    # Then, override :func:`update_instance`.
    autoreload.update_instances = _update_instances


def deactivate_autoreload() -> None:
    """Disable Plum's autoreload hack. This undoes what
    :func:`.autoreload.activate_autoreload` did."""
    global _update_instances_original
    if _update_instances_original is None:
        raise RuntimeError("Plum Autoreload module was never activated.")

    from IPython.extensions import autoreload

    autoreload.update_instances = _update_instances_original


_autoload = os.environ.get("PLUM_AUTORELOAD", "0").lower()
"""str: Value of `PLUM_AUTORELOAD` environment variable."""

if _autoload in ("y", "yes", "t", "true", "on", "1"):  # pragma: no cover
    try:
        # Try to load iPython and get the iPython session, but don't crash if
        # this does not work (for example IPython not installed, or python shell)
        from IPython import get_ipython

        ip = get_ipython()
        ext_loaded = "IPython.extensions.storemagic" in ip.extension_manager.loaded
        if (ip is not None) and ext_loaded:
            activate_autoreload()

    except ImportError:
        pass
