import threading
from concurrent.futures import ThreadPoolExecutor

import pytest


@pytest.mark.incompatible_with_mypyc
def test_registration_survives_concurrent_resolution(dispatch):
    """A registration must not be discarded as the previous batch finishes."""

    @dispatch
    def f(x: int):
        return "integer"

    exhausted = threading.Event()
    finish_resolution = threading.Event()
    registration_started = threading.Event()
    registration_finished = threading.Event()

    class PausedPending(list):
        def __iter__(self):
            yield from super().__iter__()
            exhausted.set()
            assert finish_resolution.wait(5), "Resolution was never released."

    # Pause after the old registrations have been consumed, before the pending
    # list is replaced. Native list iteration cannot use this Python hook.
    f._pending = PausedPending(f._pending)

    def add_method():
        def string_method(x: str):
            return "string"

        registration_started.set()
        f.register(string_method)
        registration_finished.set()

    with ThreadPoolExecutor(2) as pool:
        call = pool.submit(f, 1)
        try:
            assert exhausted.wait(5), "Resolution never reached the pause."
            registration = pool.submit(add_method)
            assert registration_started.wait(5), "Registration never started."
            # Without synchronization this completes immediately, appending to
            # the exhausted batch. With the lock it waits for resolution.
            registration_finished.wait(1)
        finally:
            finish_resolution.set()
        assert call.result(5) == "integer"
        registration.result(5)

    assert f("new") == "string"
    assert f(2) == "integer"
