import subprocess
from pathlib import Path

if __name__ == "__main__":
    source_dir = Path("tests/typechecked")  # Files that must be validated using `mypy`

    # Run `mypy` and get the output.
    p = subprocess.Popen(
        ["mypy", source_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate()
    assert stderr == b"", "`stderr` must be empty."
    print("Output of `mypy`:")
    print(stdout.decode())

    unvalidated_errors = []  # Errors that were not marked as intended in the source

    for line in stdout.decode().splitlines():
        # Parse line in the output of `mypy`. If it cannot be parsed, just skip it.
        try:
            path, line_number, status, message = line.split(":", 3)
        except ValueError:
            continue

        # We only need to validate errors.
        if status.lower().strip() != "error":
            continue

        # Get the line in the source that caused the error.
        with open(path, "r") as f:
            path_lines = f.read().splitlines()
        source_line = path_lines[int(line_number) - 1]

        # See if the error was intended.
        try:
            code, match = source_line.split("# mypy: E: ", 1)
            validated = match.lower() in message.lower()
        except ValueError:
            validated = False

        # If it wasn't intended, record the error.
        if not validated:
            unvalidated_errors.append(line)

    # Return failure if there are any unvalidated errors.
    if unvalidated_errors:
        print("These errors were not validated:")
        for error in unvalidated_errors:
            print(error)
        exit(1)
    else:
        print("All errors were validated!")
        exit(0)
else:
    print(__name__)
