#!/usr/bin/env python3
"""A script for configuring test infrastructure for rules_ansible tests"""

import os
import pathlib
import subprocess

HOSTS = [
    "web2",
    "web3",
]


def main() -> None:
    """The main entrypoint."""

    if "BUILD_WORKSPACE_DIRECTORY" not in os.environ:
        raise EnvironmentError(
            "BUILD_WORKSPACE_DIRECTORY is not defined. Is the process running under Bazel?"
        )

    root = pathlib.Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])

    dockerfile = root / os.environ["DOCKERFILE"]
    subprocess.run(
        ["docker", "build", "--file", str(dockerfile), "-t", "rules_ansible_test", "."],
        check=True,
    )

    for name in HOSTS:
        subprocess.run(["docker", "kill", name], check=False)
        subprocess.run(["docker", "rm", name], check=False)
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                name,
                "rules_ansible_test",
                "sleep",
                "3600",
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
