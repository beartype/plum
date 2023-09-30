import re
import types
import typing

__all__ = [
    "repr_short",
    "formatannotation",
]


class color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def colored(renderable, *clr):
    if not isinstance(renderable, str):
        renderable = repr(renderable)
    return "".join(clr) + renderable + color.END


def link(uri, label=None):
    if label is None:
        label = uri
    parameters = ""

    # OSC 8 ; params ; URI ST <name> OSC 8 ;; ST
    escape_mask = "\033]8;{};{}\033\\{}\033]8;;\033\\"

    return escape_mask.format(parameters, uri, label)


def repr_short(x):
    """Representation as a string, but in shorter form. This just calls
    :func:`typing._type_repr`.

    Args:
        x (object): Object.

    Returns:
        str: Shorter representation of `x`.
    """
    # :func:`typing._type_repr` is an internal function, but it should be available in
    # Python versions 3.8 through 3.11.
    return typing._type_repr(x)


def repr_type(typ, *clrs):
    return colored(repr_short(typ), color.BOLD, *clrs)


def formatannotation(annotation, base_module=None):
    if getattr(annotation, "__module__", None) == "typing":

        def repl(match):
            text = match.group()
            return text.removeprefix("typing.")

        return re.sub(r"[\w\.]+", repl, repr(annotation))
    if isinstance(annotation, types.GenericAlias):
        return str(annotation)
    if isinstance(annotation, type):
        if annotation.__module__ in ("builtins", base_module):
            return annotation.__qualname__
        return annotation.__module__ + "." + annotation.__qualname__
    return repr(annotation)
