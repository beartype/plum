import plum

@plum.overload
def f(x: int) -> int:
    return x

@plum.overload
def f(x: str) -> str:
    return x

@plum.dispatch  # type: ignore[misc]  # "An implementation for an overloaded function is not allowed in a stub file"
def f(x):
    pass

assert f(1) == 1
assert f("1") == "1"

# The following should raise the following errors:
# - pyright
#   - reportArgumentType: Argument of type "float" cannot be assigned to
#     parameter "x" of type "str" in function "f" "float" is not assignable to
#     "str"
#   - reportCallIssue: No overloads for "f" match the provided arguments
# - mypy:
#   - call-overload: No overload variant of "f" matches argument type "float"
f(1.0)  # type: ignore[call-overload]  # pyright: ignore[reportArgumentType,reportCallIssue]
