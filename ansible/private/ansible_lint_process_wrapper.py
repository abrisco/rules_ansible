#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence

from ansiblelint.__main__ import _run_cli_entrypoint

ANSIBLE_LINT_ARGS_FILE = "ANSIBLE_LINT_ARGS_FILE"


def _find_args_file() -> Optional[Path]:
    if ANSIBLE_LINT_ARGS_FILE in os.environ:
        args_file = Path(os.environ[ANSIBLE_LINT_ARGS_FILE])
        if not args_file.exists():
            raise FileNotFoundError(args_file)

        return args_file


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        type=Path,
        help="An optional output file to produce",
    )
    parser.add_argument(
        "lint_args",
        nargs="*",
        help="Remaining arguments to forward to ansible-lint",
    )

    if argv:
        return parser.parse_args(argv)

    return parser.parse_args()


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


def main() -> None:

    args_file = _find_args_file()
    argv = None
    if args_file:
        argv = args_file.read_text(encoding="utf-8").splitlines()
    args = parse_args(argv)

    # Create a directory to append to `PATH`
    dir_prefix = os.environ.get("TEST_TMPDIR", None)
    with tempfile.TemporaryDirectory(dir=dir_prefix) as tmp_dir:
        tmp_path = Path(tmp_dir) / "_fakepath"
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
                "HOME": tmp_dir,
                "ANSIBLE_LINT_ENTRY_POINT": __file__,
                "PATH": sys_path,
            }
        )

        lint_args = [
            sys.executable,
            __file__,
        ] + args.lint_args

        proc = subprocess.run(
            lint_args,
            env=env,
            check=False,
            capture_output=True,
        )

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


def ansible_main() -> None:
    sys.exit(_run_cli_entrypoint())


if __name__ == "__main__":
    if os.environ.get("ANSIBLE_LINT_ENTRY_POINT") == __file__:
        ansible_main()
    else:
        main()
