import typing

from rich.text import Text

from plum.repr import _repr_mimebundle_from_rich_, repr_type

from .util import rich_render


class A:
    pass


def test_repr_type():
    assert rich_render(repr_type(int)).strip() == "int"
    assert rich_render(repr_type(A)).strip() == "tests.test_repr.A"
    assert rich_render(repr_type(typing)).strip() == "typing"


def test_repr_mimebundle_from_rich():
    class A:
        def __rich_console__(self, console, options):
            yield Text("rendering")

    for v in _repr_mimebundle_from_rich_(A(), [], []).values():
        assert "rendering" in v
    assert _repr_mimebundle_from_rich_(A(), ["text/plain"], []).keys() == {"text/plain"}
    assert _repr_mimebundle_from_rich_(A(), [], ["text/plain"]).keys() == {"text/html"}
