#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, Optional, Sequence

from ansiblelint.file_utils import Lintable
from rules_python.python.runfiles import runfiles

ANSIBLE_LINT_ARGS_FILE = "ANSIBLE_LINT_ARGS_FILE"
ANSIBLE_LINT_ENTRY_POINT = "ANSIBLE_LINT_ENTRY_POINT"
RUNFILES: Optional[runfiles._Runfiles] = runfiles.Create()


def is_test() -> bool:
    """Determin if the process is running under `bazel test`.

    Returns:
        True if the process is running under `bazel test`.
    """
    if "TEST_WORKSPACE" in os.environ:
        return True

    return False


def bazel_runfiles() -> runfiles._Runfiles:
    """Get the current runfiles object.

    Returns:
        The bazel runfiles object.
    """
    if not RUNFILES:
        raise EnvironmentError(
            "Unable to create runfiles object. Is the script running under Bazel?"
        )

    return RUNFILES


def bazel_runfile_path(value: str) -> Path:
    """Return the runfile path of a given runfile key

    Args:
        value: The runfile key or `File.short_path` value.

    Returns:
        The runfile path.
    """
    if value.startswith("../"):
        key = value[len("../") :]
    elif value.startswith("rules_ansible/"):
        key = value
    elif value.startswith("external/"):
        key = value[len("external/") :]
    else:
        key = str(PurePosixPath(os.environ["TEST_WORKSPACE"]) / value)

    path = bazel_runfiles().Rlocation(key)
    if not path:
        raise ValueError(key)

    return Path(path)


def bazel_sandbox_path(value: str) -> Path:
    """Return the value of a file relative to the cwd

    Args:
        value: The path

    Returns:
        An absolute path
    """
    path = Path(value)
    if path.is_absolute():
        return path

    return Path.cwd() / path


def _find_args_file() -> Optional[Path]:
    """Attempt to find a file containing command line arguments.

    This is required to work around:
    https://github.com/bazelbuild/bazel/issues/16076

    Returns:
        The path to a uniquely named args file.
    """
    if ANSIBLE_LINT_ARGS_FILE in os.environ:
        args_file = Path(os.environ[ANSIBLE_LINT_ARGS_FILE])
        if not args_file.exists():
            raise FileNotFoundError(args_file)

        return args_file


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: An optional set of args to use instead of `sys.argv[1:]`

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser()

    file_type = bazel_runfile_path if is_test() else bazel_sandbox_path

    parser.add_argument(
        "--output",
        type=Path,
        help="An optional output file to produce",
    )
    parser.add_argument(
        # This argument is used for sanitizing logs
        "--package",
        type=str,
        required=True,
        help="The package of the playbook target used for linting.",
    )
    parser.add_argument(
        "--playbook",
        type=file_type,
        required=True,
        help="The ansible playbook to lint",
    )
    parser.add_argument(
        "--config_file",
        type=file_type,
        required=True,
        help="The ansible config file.",
    )
    parser.add_argument(
        "--lint_config_file",
        type=file_type,
        required=True,
        help="The ansible-lint config file.",
    )
    parser.add_argument(
        "lint_args",
        nargs="*",
        default=[],
        help="Remaining arguments to forward to ansible-lint",
    )

    if argv:
        args = parser.parse_args(argv)
    else:
        args = parser.parse_args()

    # Update lint args to use explicitly parsed values
    args.lint_args = (
        [
            "--config-file",
            str(args.lint_config_file),
            "--project-dir",
            str(args.playbook.parent),
        ]
        + args.lint_args
        + [str(args.playbook)]
    )

    return args


def load_entrypoints() -> Dict[str, str]:
    """Load entrypoints files into a dict

    Returns:
        A mapping of entrypoints to their text contents.
    """
    lookup = bazel_sandbox_path
    entrypoints = {
        "ansible": "ansible/private/ansible.py",
        "ansible-config": "ansible/private/ansible_config.py",
        "ansible-playbook": "ansible/private/ansible_playbook.py",
        "ansible-doc": "ansible/private/ansible_doc.py",
    }

    # Convert to runfiles path
    if is_test():
        lookup = bazel_runfile_path
        entrypoints = {
            name: f"rules_ansible/{path}" for name, path in entrypoints.items()
        }

    return {
        name: lookup(path).read_text(encoding="utf-8")
        for name, path in entrypoints.items()
    }


def write_entrypoint(path: Path, content: str) -> None:
    """A helper function for writing executable files

    Args:
        path: The path of the file.
        content: Content to write.
    """
    path.write_text(content, encoding="utf-8")
    path.chmod(0o700)


def lint_main(
    config: Path,
    playbook_dir: Path,
    capture_output: bool = True,
    args: Iterable[str] = [],
    temp_dir: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """The entrypoint for running `ansible-lint` in a Bazel action or test.

    Args:
        config: The path to the ansible config file.
        playbook_dir: The path to the ansible playbook directory.
        capture_output: The value of `subprocess.run.capture_output`.
        args: Arguments to pass to ansible-lint
        temp_dir: An optional base directory to use for writing files reqired by
            linting. if not set, a temporary directory will be generated separately.

    Returns:
        The results of the ansible-lint `subprocess.run`.
    """

    # Generate temp directories within the sandbox
    dir_prefix = (
        str(temp_dir) if temp_dir else os.environ.get("TEST_TMPDIR", str(Path.cwd()))
    )

    # Create a directory to append to `PATH`
    tmp_path = Path(tempfile.mkdtemp(dir=dir_prefix)) / "_fakepath"
    tmp_path.mkdir(exist_ok=True, parents=True)

    interp_name = Path(sys.executable).name

    for tool, content in load_entrypoints().items():
        entrypoint_content = "\n".join(
            [
                f"#!/usr/bin/env {interp_name}",
                content,
            ]
        )

        write_entrypoint(tmp_path / tool, entrypoint_content)

    # Create a symlink to the python interpreter
    for ext in ["", ".exe"]:
        for name in set(["python3", interp_name]):
            interpreter = tmp_path / (name + ext)
            interpreter.symlink_to(sys.executable)

    env = dict(os.environ)
    sys_path = str(tmp_path) + os.pathsep + env.get("PATH", "")
    env.update(
        {
            "HOME": str(tmp_path),
            ANSIBLE_LINT_ENTRY_POINT: __file__,
            "PATH": sys_path,
            "ANSIBLE_CONFIG": str(config),
            "ANSIBLE_PLAYBOOK_DIR": str(playbook_dir),
        }
    )
    print(playbook_dir)

    lint_args = [
        sys.executable,
        __file__,
    ] + args

    return subprocess.run(
        lint_args,
        env=env,
        check=False,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.STDOUT if capture_output else None,
    )


def main() -> None:
    """The main entrypoint of the script"""

    args_file = _find_args_file()
    argv = None
    if args_file:
        argv = args_file.read_text(encoding="utf-8").splitlines()
    args = parse_args(argv)

    proc = lint_main(
        config=args.config_file, playbook_dir=args.playbook.parent, args=args.lint_args
    )

    if proc.returncode:
        stdout = proc.stdout.decode(encoding="utf-8")
        stdout = stdout.replace(str(args.playbook.parent), args.package)

        print(stdout, file=sys.stderr)
        sys.exit(proc.returncode)

    if args.output:
        args.output.write_bytes(b"")


class AnsibleLintable(Lintable):
    """A wrapper class for an Ansible Lintable that restores paths of resolved symlinks to their original values.

    This allows linting to occur in the Bazel sandbox.
    """

    def __init__(
        self,
        name: str | Path,
        *args,
        **kwargs,
    ):
        orig_path = Path.cwd() / name
        super().__init__(name=name, *args, **kwargs)

        self.path = self.abspath = orig_path
        self.name = self.filename = str(orig_path)


def ansible_main() -> None:
    """The ansible-lint entrypoint for directly invoking `ansible-lint`."""
    # Patch ansible-lint to avoid resolving symlinks
    import ansiblelint.file_utils

    ansiblelint.file_utils.Lintable = AnsibleLintable

    from ansiblelint.__main__ import _run_cli_entrypoint

    _run_cli_entrypoint()


if __name__ == "__main__":
    if os.environ.get(ANSIBLE_LINT_ENTRY_POINT) == __file__:
        ansible_main()
    else:
        main()
