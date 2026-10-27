import warnings
from typing import Annotated, get_args
from typing_extensions import Doc

import pytest

from plum import ModuleType, resolve_type_hint


@pytest.mark.parametrize(
    "metadata",
    [
        Doc("Input documentation."),
        "units",
        {"units": "m"},
        ModuleType("builtins", "float"),
    ],
)
def test_resolve_annotated_metadata_is_opaque(metadata):
    """Resolve the wrapped hint without interpreting or replacing its metadata."""
    hint = Annotated[ModuleType("builtins", "int"), metadata]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        resolved = resolve_type_hint(hint)
    assert get_args(resolved)[0] is int
    assert get_args(resolved)[1] is metadata


def test_dispatch_with_documented_annotations(dispatch):
    """Documented argument and return hints must not emit unresolved-hint warnings."""

    @dispatch
    def f(x: Annotated[int, "Input."]) -> Annotated[int, "Output."]:
        return x

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert f(3) == 3
        assert f(4) == 4
