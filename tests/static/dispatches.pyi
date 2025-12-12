from typing_extensions import assert_type

import plum

# Pyright errors:
#   - Function declaration "f" is obscured by a declaration of the same name
@plum.dispatch
def f(x: int) -> str:  # pyright: ignore[reportRedeclaration]
    return str(x)

# Mypy errors:
#   - Cannot infer return type (`Expression is of type "Any", not "str"`)
assert_type(f(1), str)  # type: ignore[assert-type]

# Mypy errors:
#   - Name "f" already defined on line ...
@plum.dispatch  # type: ignore[no-redef]
def f(x: str) -> str:
    return x

# Mypy errors:
#   - Cannot infer return type (`Expression is of type "Any", not "str"`)
assert_type(f(1), str)  # type: ignore[assert-type]

# Mypy errors:
#   - Argument 1 to "f" has incompatible type "str"; expected "int"
#   - Cannot infer return type (`Expression is of type "Any", not "str"`)
assert_type(f("1"), str)  # type: ignore[arg-type,assert-type]
