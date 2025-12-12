import plum

@plum.overload
def f(x: int) -> int:
    return x

@plum.overload
def f(x: str) -> str:
    return x

# MyPy errors:
# - An implementation for an overloaded function is not allowed in a stub file
@plum.dispatch  # type: ignore[misc]
def f(x):
    pass

assert f(1) == 1
assert f("1") == "1"

# - MyPy errors:
#   - call-overload: No overload variant of "f" matches argument type "float"
# - PyRight errors:
#   - reportArgumentType: Argument of type "float" cannot be assigned to
#     parameter "x" of type "str" in function "f" "float" is not assignable to
#     "str"
#   - reportCallIssue: No overloads for "f" match the provided arguments
f(1.0)  # type: ignore[call-overload]  # pyright: ignore[reportArgumentType,reportCallIssue]
