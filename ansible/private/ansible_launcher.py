#!/usr/bin/env python

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from rules_python.python.runfiles import runfiles

ENV_ANSIBLE_BZL_PLAYBOOK = "ANSIBLE_BZL_PLAYBOOK"
ENV_ANSIBLE_BZL_WORKSPACE_NAME = "ANSIBLE_BZL_WORKSPACE_NAME"
ENV_ANSIBLE_BZL_PACKAGE = "ANSIBLE_BZL_PACKAGE"
ENV_ANSIBLE_BZL_ANSIBLE = "ANSIBLE_BZL_ANSIBLE"
ENV_ANSIBLE_BZL_ANSIBLE_VAULT = "ANSIBLE_BZL_ANSIBLE_VAULT"
ENV_ANSIBLE_BZL_ARGS = "ANSIBLE_BZL_ARGS"
ENV_ANSIBLE_BZL_VAULT_FILES = "ANSIBLE_BZL_VAULT_FILES"
ENV_ANSIBLE_BZL_CONFIG = "ANSIBLE_BZL_CONFIG"
ENV_ANSIBLE_BZL_LAUNCHER_NAME = "ANSIBLE_BZL_LAUNCHER_NAME"
ENV_ANSIBLE_BZL_INVENTORY_HOSTS = "ANSIBLE_BZL_INVENTORY_HOSTS"

RUNFILES: Optional[runfiles._Runfiles] = runfiles.Create()


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
        key = value[3:]
    else:
        key = "{}/{}".format(os.environ[ENV_ANSIBLE_BZL_WORKSPACE_NAME], value)

    path = bazel_runfiles().Rlocation(key)
    if not path:
        raise ValueError(key)

    return Path(path)


def get_playbook() -> Path:
    """Get the path of the playbook to run.

    Returns:
        The path to the playbook to run
    """
    env = os.getenv(ENV_ANSIBLE_BZL_PLAYBOOK)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_PLAYBOOK))
    return bazel_runfile_path(env)


def get_inventory_hosts() -> Path:
    """Get the path to the inventory `hosts` file.

    Returns:
        The path to `hosts`.
    """
    env = os.getenv(ENV_ANSIBLE_BZL_INVENTORY_HOSTS)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_INVENTORY_HOSTS))
    return bazel_runfile_path(env)


def get_ansible_config() -> Path:
    """Get the path to the ansible.cfg file given to the `ansible_playbook` rule.

    Returns:
        The path to the ansible config
    """
    env = os.getenv(ENV_ANSIBLE_BZL_CONFIG)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_CONFIG))
    return bazel_runfile_path(env)


def get_ansible_package() -> str:
    """Return the package name of the `ansible_playbook` target

    Returns:
        The Bazel package name of the current target.
    """
    env = os.getenv(ENV_ANSIBLE_BZL_PACKAGE)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_PACKAGE))
    return env


def get_ansible_bin() -> Path:
    """Locate the ansible-playbook binary

    Returns:
        A python entrypoint.
    """
    path = Path(__file__).parent / "ansible-playbook.py"
    if not path.exists():
        raise FileNotFoundError(path)

    return path


def get_ansible_vault_bin() -> Path:
    """Locate the ansible-vault binary

    Returns:
        A python entrypoint.
    """
    path = Path(__file__).parent / "ansible-vault.py"
    if not path.exists():
        raise FileNotFoundError(path)

    return path


def get_bazel_workspace_root() -> Path:
    """Get the workspace root of the current target

    Returns:
        The Bazel workspace root.
    """
    env = os.getenv("BUILD_WORKSPACE_DIRECTORY")
    if not env:
        raise EnvironmentError("BUILD_WORKSPACE_DIRECTORY is not set")
    return Path(env)


def get_ansible_args() -> List[str]:
    """Return a list of extra args for running ansible.

    Returns:
        A list of arguments to pass to `ansible-playbook.`
    """
    env = os.getenv(ENV_ANSIBLE_BZL_ARGS)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_ARGS))
    return json.loads(env)


def get_ansible_vault_files() -> List[str]:
    """Return any vault encrypted files passed to the `ansible_playbook` target.

    Returns:
        A list of vault files
    """
    env = os.getenv(ENV_ANSIBLE_BZL_VAULT_FILES)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_VAULT_FILES))
    return [bazel_runfile_path(file) for file in json.loads(env)]


def find_vault_key() -> Optional[Path]:
    """Locate the vault password file

    Returns:
        The path to the vault password file if found.
    """
    # This assumes inventories are structured as `./inventories/<environment>/hosts`.
    # So if the grand parent of the hosts file is not a directory named `inventories`,
    # we assume the vault pass directory is structured in the same way.
    hosts_file = get_inventory_hosts()
    if hosts_file.parent.parent.name == "inventories":
        vault_pass_file = Path(".vault_pass") / hosts_file.parent.name
    else:
        vault_pass_file = Path(".vault_pass")

    # First look in the package directory for vault key
    package_dir = get_bazel_workspace_root() / get_ansible_package()
    vault_key = package_dir / vault_pass_file

    # Check the parent directory
    if not vault_key.exists():
        vault_key = package_dir.parent / vault_pass_file

    # if the key doesn't exist, try the workspace root
    if not vault_key.exists():
        vault_key = get_bazel_workspace_root() / vault_pass_file

    if vault_key.exists():
        return vault_key

    return None


def delete_files(files: List[Path]) -> None:
    """Delete a list of files

    Args:
        files: The files to delete.
    """
    for file in files:
        file.unlink()


def decrypt_vault(
    vault_files: List[Path],
    vault_key: Optional[Path],
) -> List[Path]:
    """Decrypt vault files for use by ansible.

    Files are expected to have a suffix matching the name of the `ansible_playbook` target and
    `.vaultfile`. This allows us to decrypt the files into the expected location with the stripped
    suffix so the playbooks have access to decrypted content without leaving decrypted content
    in the repo.

    Args:
        vault_files: A list of paths to ansible-vault encrypted files
        vault_key: The path to the vault password file. E.g. `/ansible/.vault-pass/<inventory>`

    Returns:
        Paths to the decrypted files.
    """

    environ = os.environ.copy()

    command = [
        sys.executable,
        str(get_ansible_vault_bin()),
        "decrypt",
    ]

    # Otherwise, hope that `ansible-vault` can find it
    if vault_key and vault_key.exists():
        command.extend(
            [
                "--vault-password-file",
                str(vault_key),
            ]
        )

    # This value must match that defined by the `AnsibleVaultCopier` action
    suffix = ".vaultfile"

    decrypted_files = []
    try:
        for file in vault_files:
            # Now make sure to "install" the files by stripping the `.vaultfile` extension
            decrypted_file = Path(str(file)[: -len(suffix)])

            vault_command = command + [
                str(file),
                "--output",
                str(decrypted_file),
            ]

            subprocess.run(vault_command, check=True, env=environ)
            decrypted_file.chmod(0o600)
            decrypted_files.append(decrypted_file)
    except (subprocess.CalledProcessError, KeyboardInterrupt):
        delete_files(decrypted_files)
        raise

    return decrypted_files


def run_ansible(
    playbook: Path,
    vault_password_file: Optional[Path] = None,
    extra_args: List[str] = [],
) -> None:
    """Run ansible-playbook

    Args:
        playbook: The path to the playbook to run.
        vault_password_file: The vault password file to use. E.g. `/ansible/.vault-pass/<inventory>`
        extra_args: Additional arguments to pass to the `ansible-playbook` call.
    """
    ansible = get_ansible_bin()

    inventory = get_inventory_hosts().parent

    command = [
        str(ansible),
        str(playbook),
        f"--inventory={inventory}",
    ]

    if vault_password_file and vault_password_file.exists():
        command.append(
            f"--vault-password-file={vault_password_file}",
        )

    command.extend(sys.argv[1:])
    command.extend(extra_args)

    env = os.environ.copy()
    cfg = get_ansible_config()
    if cfg and "ANSIBLE_CONFIG" not in env:
        env.update({"ANSIBLE_CONFIG": str(cfg)})

    os.execve(sys.executable, [sys.executable] + command, env)


def main() -> None:
    """The main entrypoint of the script."""

    playbook = get_playbook()
    if not playbook.exists():
        raise FileNotFoundError("Requested playbook not found", playbook)

    # Check for an explicit vault key
    vault_key = find_vault_key()

    # Check for any vault files
    vault_files = decrypt_vault(
        vault_files=get_ansible_vault_files(),
        vault_key=vault_key,
    )

    try:
        run_ansible(
            playbook=playbook,
            vault_password_file=vault_key,
            extra_args=get_ansible_args(),
        )
    finally:
        delete_files(vault_files)


if __name__ == "__main__":
    main()
