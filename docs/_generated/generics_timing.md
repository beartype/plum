| Call | Scenario | µs / call | vs faithful |
| :--- | :--- | ---: | ---: |
| `f(B(1))` | faithful — bare `B` overload | 4.01 | 1.0× |
| `f(A(1))` | generic — `A[Any]` fallback | 5.81 | 1.4× |
| `f(A[int](1))` | generic — `A[int]` overload | 6.28 | 1.6× |
