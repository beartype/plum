import gc
import os

from .type import Type, Union
from .dispatcher import Dispatcher

__all__ = ["activate", "deactivate"]


def _update_instances(old, new):
    """Use garbage collector to find all instances that refer to the old
    class definition and update their __class__ to point to the new class
    definition"""

    refs = gc.get_referrers(old)

    updated_plum_type = False

    for ref in refs:
        if type(ref) is old:
            ref.__class__ = new
        elif type(ref) == Type:
            updated_plum_type = True
            ref._type = new

    # if we updated a plum type, then
    # use the gc to get all dispatchers and clear
    # their cache
    if updated_plum_type:
        refs = gc.get_referrers(Dispatcher)
        for ref in refs:
            if type(ref) is Dispatcher:
                ref.clear_cache()


_update_instances_original = None


def activate():
    """
    Pirate autoreload's `update_instance` function to handle Plum types.
    """
    from IPython.extensions import autoreload
    from IPython.extensions.autoreload import update_instances

    # First, cache the original method so we can deactivate ourselves.
    global _update_instances_original
    if _update_instances_original is None:
        _update_instances_original = autoreload.update_instances

    # Then, override the update_instance method
    setattr(autoreload, "update_instances", _update_instances)


def deactivate():
    """
    Disable Plum's autoreload hack.
    """
    global _update_instances_original
    if _update_instances_original is None:  # pragma: no cover
        raise RuntimeError("Plum Autoreload module was never activated.")

    from IPython.extensions import autoreload

    setattr(autoreload, "update_instances", _update_instances_original)


# Detect `PLUM_AUTORELOAD` env variable
_autoload = os.environ.get("PLUM_AUTORELOAD", "0").lower()
if _autoload in ("y", "yes", "t", "true", "on", "1"):  # pragma: no cover
    _autoload = True
else:
    _autoload = False

if _autoload:  # pragma: no cover
    try:
        # Try to load IPython and get the iPython session, but don't crash if
        # this does not work (for example IPython not installed, or python shell)
        from IPython import get_ipython

        ip = get_ipython()
        if ip is not None:
            if "IPython.extensions.storemagic" in ip.extension_manager.loaded:
                activate()

    except ImportError:
        pass
