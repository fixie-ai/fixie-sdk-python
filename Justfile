# This is the main Justfile for the Fixie SDK repo.
# Just is a tool to streamline common development commands. You don't need it
# to use this SDK, but it is helpful if you'd like to contribute.
# To install Just, see: https://github.com/casey/just#installation

# Allow for positional arguments in Just receipes.
set positional-arguments := true

# Dump the Python stack trace on crashes
export PYTHONFAULTHANDLER := "1"

# Default recipe that runs if you type "just"
default: format check test

# Install dependencies for local development
install:
    pip install poetry==1.7.1
    poetry install --sync

# Format code
format:
    poetry run autoflake . --remove-all-unused-imports --quiet --in-place -r
    poetry run isort . --force-single-line-imports
    poetry run black .

# Run static code checks
check:
    poetry check
    poetry run black . --check
    poetry run isort . --check --force-single-line-imports
    poetry run autoflake . --check --quiet --remove-all-unused-imports -r
    poetry run mypy .
    poetry run deptry .

# Run tests
test *ARGS="--dist loadgroup -n auto .":
    poetry run pytest {{ARGS}}

# Run tests with verbose output
test-verbose PATH=".":
    poetry run pytest -vv --log-cli-level=INFO {{PATH}}

# Run a Python REPL in poetry's venv
python *FLAGS:
    poetry run python {{FLAGS}}

# Run the voice client locally
run-voice *FLAGS:
    poetry run python fixie_sdk/voice/client.py {{FLAGS}}
