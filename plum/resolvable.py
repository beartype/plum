import abc
import builtins
import logging

__all__ = [
    "ResolutionError",
    "Resolvable",
    "Promise",
    "referentiables",
    "Referentiable",
]

log = logging.getLogger(__name__)


class ResolutionError(RuntimeError):
    """Object could not be resolved."""


class Resolvable(abc.ABC):
    """An object that can be resolved and compared."""

    @abc.abstractmethod
    def resolve(self):
        """Resolve the object.

        Returns:
            Promised object.
        """


class Promise(Resolvable):
    """An object that is promised to be resolvable when asked for."""

    def __init__(self):
        self._obj = None

    def deliver(self, obj):
        """Deliver the promise.

        Args:
            obj: The object to deliver.
        """
        self._obj = obj

    def resolve(self):
        if self._obj is None:
            raise ResolutionError("Promise was not kept.")
        else:
            return self._obj


referentiables = []  #: Referentiable classes.

# Hook into `builtins.__build_class__` to track class creation. Here be dragons...
if hasattr(builtins, "__build_class__"):
    _builtin_build_class = builtins.__build_class__

    def __build_class__(*args, **kw_args):
        instance = _builtin_build_class(*args, **kw_args)
        # This will be called before `Referentiable.__new__`.
        if len(referentiables) == 0 or referentiables[-1] is not instance:
            if hasattr(instance, "__track__") and not instance.__track__:
                pass  # Don't track the class.
            else:
                referentiables.append(instance)
        return instance

    builtins.__build_class__ = __build_class__
else:  # pragma: no cover
    log.warning(
        '"builtins.__build_class__" not available. '
        'Please be careful to set the metaclass to "Referentiable" wherever '
        "dispatch within a class is used."
    )


# As a backup, expose a metaclass to track referentiables.


def Referentiable(*args):
    """Create a metaclass that tracks referentiables.

    Args:
        base (type): Type to subtype. Defaults to `type`.

    Returns:
        type: Referentiable metaclass that subtypes `base`.
    """
    if len(args) > 1:
        # Function was passed as metaclass without calling it.
        return Referentiable()(*args)
    elif len(args) == 1:
        # Function was passed a metaclass to subtype.
        Base = args[0]
    else:
        # Function was not passed a metaclass to subtype. Default to `type`.
        Base = type

    class Meta(Base):
        __track__ = False

        def __new__(*args, **kw_args):
            instance = Base.__new__(*args, **kw_args)
            # This will be called before `builtins.__build_class__`.
            referentiables.append(instance)
            return instance

    return Meta
