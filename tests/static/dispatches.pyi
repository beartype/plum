from typing_extensions import assert_type

import plum

# PyRight errors:
#   - Function declaration "f" is obscured by a declaration of the same name
@plum.dispatch
def f(x: int) -> str:  # pyright: ignore[reportRedeclaration]
    return str(x)

# Pyright errors:
#  - Argument missing for parameter "y"
#  - "assert_type" mismatch: expected "str" but received "Unknown"
assert_type(f(1), str)  # pyright: ignore[reportCallIssue,reportAssertTypeFailure]

# MyPy errors:
#   - Name "f" already defined on line ...
@plum.dispatch  # type: ignore[no-redef]
def f(x: str) -> str:  # pyright: ignore[reportRedeclaration]
    return x

# Pyright errors:
#  - Argument missing for parameter "y"
#  - "assert_type" mismatch: expected "str" but received "Unknown"
assert_type(f(1), str)  # pyright: ignore[reportCallIssue,reportAssertTypeFailure]

# MyPy errors:
#   - Argument 1 to "f" has incompatible type "str"; expected "int"
assert_type(f("1"), str)  # type: ignore[arg-type]

# Mypy errors:
#   - `Name "f" already defined on line ...`
# Pyright errors:
#  - Argument missing for parameter "y"
@plum.dispatch  # type: ignore[no-redef]
def f(x: int, y: int) -> tuple[str, str]:
    return f(x), f(y)  # pyright: ignore[reportCallIssue]

# Mypy errors:
#   - Expression is of type "str", not "tuple[str, str]"
#   - Too many arguments for "f"
assert_type(f(1, 2), tuple[str, str])  # type: ignore[assert-type,call-arg]
