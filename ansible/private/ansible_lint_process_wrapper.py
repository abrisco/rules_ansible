#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Optional, Sequence

from ansiblelint.__main__ import _run_cli_entrypoint
from ansiblelint.file_utils import Lintable
from ansiblelint.constants import FileType
from rules_python.python.runfiles import runfiles

ANSIBLE_LINT_ARGS_FILE = "ANSIBLE_LINT_ARGS_FILE"
ANSIBLE_LINT_ENTRY_POINT = "ANSIBLE_LINT_ENTRY_POINT"
RUNFILES: Optional[runfiles._Runfiles] = runfiles.Create()


def bazel_runfiles() -> runfiles._Runfiles:
    if not RUNFILES:
        raise EnvironmentError(
            "Unable to create runfiles object. Is the script running under Bazel?"
        )

    return RUNFILES


def bazel_runfile_path(value: str) -> Path:

    if value.startswith("../"):
        key = value
    else:
        key = "{}/{}".format(os.environ["TEST_WORKSPACE"], value)

    path = bazel_runfiles().Rlocation(key)
    if not path:
        raise ValueError(key)

    return Path(path)


def bazel_sandbox_path(value: str) -> Path:

    path = Path(value)
    if path.is_absolute():
        return path

    return Path.cwd() / path


def _find_args_file() -> Optional[Path]:
    if ANSIBLE_LINT_ARGS_FILE in os.environ:
        args_file = Path(os.environ[ANSIBLE_LINT_ARGS_FILE])
        if not args_file.exists():
            raise FileNotFoundError(args_file)

        return args_file


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    file_type = bazel_sandbox_path
    if "TEST_WORKSPACE" in os.environ:
        file_type = bazel_runfile_path

    parser.add_argument(
        "--output",
        type=Path,
        help="An optional output file to produce",
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
            str(args.config_file),
            "--project-dir",
            str(args.playbook.parent),
        ]
        + args.lint_args
        + [str(args.playbook)]
    )

    return args


ANSIBLE_ENTRYPOINT = """\
# -*- coding: utf-8 -*-
import re
import sys
from ansible.cli.adhoc import main
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])
    sys.exit(main())
"""

ANSIBLE_CONFIG_ENTRYPOINT = """\
# -*- coding: utf-8 -*-
import re
import sys
from ansible.cli.config import main
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(main())
"""

ANSIBLE_PLAYBOOK_ENTRYPOINT = """\
# -*- coding: utf-8 -*-
import re
import sys
from ansible.cli.playbook import main
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(main())
"""

ENTRYPOINTS = {
    "ansible": ANSIBLE_ENTRYPOINT,
    "ansible-config": ANSIBLE_CONFIG_ENTRYPOINT,
    "ansible-playbook": ANSIBLE_PLAYBOOK_ENTRYPOINT,
}


def write_entrypoint(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o700)


def lint_main(capture_output: bool = True, args: Iterable[str] = []) -> None:

    # Generate temp directories within the sandbox
    dir_prefix = os.environ.get("TEST_TMPDIR", str(Path.cwd()))

    # Create a directory to append to `PATH`
    tmp_path = Path(tempfile.mkdtemp(dir=dir_prefix)) / "_fakepath"
    tmp_path.mkdir(exist_ok=True, parents=True)

    for tool, content in ENTRYPOINTS.items():
        entrypoint_content = "\n".join(
            [
                "#!/usr/bin/env {}".format(Path(sys.executable).name),
                content,
            ]
        )

        write_entrypoint(tmp_path / tool, entrypoint_content)

    # Create a symlink to the python interpreter
    for ext in ["", ".exe"]:
        interpreter = tmp_path / ("python3" + ext)
        interpreter.symlink_to(sys.executable)

    env = dict(os.environ)
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
        capture_output=capture_output,
    )


def main() -> None:

    args_file = _find_args_file()
    argv = None
    if args_file:
        argv = args_file.read_text(encoding="utf-8").splitlines()
    args = parse_args(argv)

    proc = lint_main(args=args.lint_args)

    if proc.returncode:
        stdout = proc.stdout.decode(encoding="utf-8")
        stderr = proc.stderr.decode(encoding="utf-8")

        # The first lint argument is always the path to the playbook
        playbook = Path(args.lint_args[0])
        if playbook.exists():
            abs_parent = playbook.resolve().parent
            stdout = stdout.replace(str(abs_parent), "{PLAYBOOK_DIR}")
            stderr = stderr.replace(str(abs_parent), "{PLAYBOOK_DIR}")

        print(stdout, file=sys.stdout)
        print(stderr, file=sys.stderr)
        sys.exit(proc.returncode)

    if args.output:
        args.output.write_bytes(b"")


class AnsibleLintable(Lintable):
    """A wrapper class for an Ansible Lintable that restores paths of resolved symlinks to their original values.

    This allows linting to occur in the Bazel sandbox.
    """

    def __init__(
        self,
        name: str,
        content: Optional[str] = None,
        kind: Optional[FileType] = None,
    ):
        orig_path = Path.cwd() / name
        super().__init__(name=name, content=content, kind=kind)
        self.path = self.abspath = orig_path
        self.name = self.filename = str(orig_path)


def ansible_main() -> None:
    # Patch ansible-lint to avoid resolving symlinks
    import ansiblelint.file_utils

    ansiblelint.file_utils.Lintable = AnsibleLintable

    sys.exit(_run_cli_entrypoint())


if __name__ == "__main__":
    if os.environ.get(ANSIBLE_LINT_ENTRY_POINT) == __file__:
        ansible_main()
    else:
        main()
