"""A process wrapper for running ansible-lint."""

import argparse
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

from ansiblelint.file_utils import Lintable
from python.runfiles import Runfiles

ANSIBLE_LINT_ARGS_FILE = "ANSIBLE_LINT_ARGS_FILE"
ANSIBLE_LINT_ENTRY_POINT = "ANSIBLE_LINT_ENTRY_POINT"
RUNFILES: Optional[Runfiles] = None


def is_test() -> bool:
    """Determin if the process is running under `bazel test`.

    Returns:
        True if the process is running under `bazel test`.
    """
    if "TEST_WORKSPACE" in os.environ:
        return True

    return False


def _rlocation(rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        rlocationpath: The runfile key

    Returns:
        The requested runifle.
    """
    if not RUNFILES:
        raise EnvironmentError("Failed to locate runfiles")
    runfile = RUNFILES.Rlocation(rlocationpath, os.getenv("TEST_WORKSPACE"))
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def _execpath(value: str) -> Path:
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
        return _rlocation(os.environ[ANSIBLE_LINT_ARGS_FILE])


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: An optional set of args to use instead of `sys.argv[1:]`

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser()

    file_type = _rlocation if is_test() else _execpath

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
    entrypoints = {
        "ansible-config": "private/scripts/ansible_config.py",
        "ansible-doc": "private/scripts/ansible_doc.py",
        "ansible-galaxy": "private/scripts/ansible_galaxy.py",
        "ansible-playbook": "private/scripts/ansible_playbook.py",
        "ansible": "private/scripts/ansible.py",
    }

    # Convert to runfiles path
    if is_test():
        try:
            return {
                name: _rlocation(f"rules_ansible/{path}").read_text(encoding="utf-8")
                for name, path in entrypoints.items()
            }
        except FileNotFoundError:
            return {
                name: _rlocation(f"_main/{path}").read_text(encoding="utf-8")
                for name, path in entrypoints.items()
            }

    return {
        name: _execpath(path).read_text(encoding="utf-8")
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
    additional_env: Optional[Dict[str, str]] = None,
    capture_output: bool = True,
    args: Iterable[str] = [],
    temp_dir: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """The entrypoint for running `ansible-lint` in a Bazel action or test.

    Args:
        additional_env: Additional environment variables to set.
        playbook_dir: The path to the ansible playbook directory.
        capture_output: The value of `subprocess.run.capture_output`.
        args: Arguments to pass to ansible-lint
        temp_dir: An optional base directory to use for writing files required by
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

    for tool, content in load_entrypoints().items():
        entrypoint_content = "\n".join(
            [
                f"#!{sys.executable}",
                content,
            ]
        )

        write_entrypoint(tmp_path / tool, entrypoint_content)

    env = dict(os.environ)
    if additional_env:
        env.update(additional_env)

    sys_path = str(tmp_path) + os.pathsep + env.get("PATH", "")
    env.update(
        {
            "HOME": str(tmp_path),
            ANSIBLE_LINT_ENTRY_POINT: __file__,
            "PATH": sys_path,
        }
    )

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
    if "RULES_ANSIBLE_DEBUG" in os.environ:
        logging.basicConfig(level=logging.DEBUG)

    global RUNFILES
    RUNFILES = Runfiles.Create()

    args_file = _find_args_file()
    argv = None
    if args_file:
        argv = args_file.read_text(encoding="utf-8").splitlines()
    args = parse_args(argv)

    env = {
        "ANSIBLE_CONFIG": str(args.config_file),
        "ANSIBLE_PLAYBOOK_DIR": str(args.playbook.parent),
    }

    proc = lint_main(args=args.lint_args, additional_env=env)

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
