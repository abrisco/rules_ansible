#!/usr/bin/env python3

import os
import sys
import tempfile
from pathlib import Path

import rules_ansible.private.ansible_lint_process_wrapper as ansible_lint


def main() -> None:
    """The main entrypoint of the script."""
    working_dir = os.environ.get(
        "BUILD_WORKING_DIRECTORY", os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    )
    if not working_dir:
        raise EnvironmentError(
            "BUILD_WORKING_DIRECTORY or BUILD_WORKSPACE_DIRECTORY is not set. Is the process running under Bazel?"
        )

    os.chdir(working_dir)

    with tempfile.TemporaryDirectory() as tmp_dir:
        proc = ansible_lint.lint_main(
            capture_output=False, args=sys.argv[1:], temp_dir=Path(tmp_dir)
        )

    sys.exit(proc.returncode)


if __name__ == "__main__":
    if os.environ.get(ansible_lint.ANSIBLE_LINT_ENTRY_POINT) == __file__:
        ansible_lint.ansible_main()
    else:
        main()
