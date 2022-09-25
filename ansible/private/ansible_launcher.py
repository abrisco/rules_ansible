#!/usr/bin/env python

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

ENV_ANSIBLE_BZL_PLAYBOOK = "ANSIBLE_BZL_PLAYBOOK"
ENV_ANSIBLE_BZL_PACKAGE = "ANSIBLE_BZL_PACKAGE"
ENV_ANSIBLE_BZL_ANSIBLE = "ANSIBLE_BZL_ANSIBLE"
ENV_ANSIBLE_BZL_ANSIBLE_VAULT = "ANSIBLE_BZL_ANSIBLE_VAULT"
ENV_ANSIBLE_BZL_ARGS = "ANSIBLE_BZL_ARGS"
ENV_ANSIBLE_BZL_VAULT_FILES = "ANSIBLE_BZL_VAULT_FILES"
ENV_ANSIBLE_BZL_CONFIG = "ANSIBLE_BZL_CONFIG"
ENV_ANSIBLE_BZL_LAUNCHER_NAME = "ANSIBLE_BZL_LAUNCHER_NAME"
ENV_ANSIBLE_BZL_INVENTORY_HOSTS = "ANSIBLE_BZL_INVENTORY_HOSTS"


def get_playbook(playbooks_dir: Optional[Path] = None) -> Path:
    if not playbooks_dir:
        playbooks_dir = get_target_package_dir()
    env = os.getenv(ENV_ANSIBLE_BZL_PLAYBOOK)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_PLAYBOOK))
    return playbooks_dir / env


def get_inventory_hosts(playbooks_dir: Optional[Path] = None) -> Path:
    if not playbooks_dir:
        playbooks_dir = get_target_package_dir()
    env = os.getenv(ENV_ANSIBLE_BZL_INVENTORY_HOSTS)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_INVENTORY_HOSTS))
    return playbooks_dir / env


def get_ansible_package() -> str:
    env = os.getenv(ENV_ANSIBLE_BZL_PACKAGE)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_PACKAGE))
    return env


def get_ansible_bin() -> Path:
    path = Path(__file__).parent / "ansible-playbook.py"
    if not path.exists():
        raise FileNotFoundError(path)

    return path


def get_ansible_vault_bin() -> Path:
    path = Path(__file__).parent / "ansible-vault.py"
    if not path.exists():
        raise FileNotFoundError(path)

    return path


def get_target_package_dir() -> Path:
    env = os.getenv(ENV_ANSIBLE_BZL_PACKAGE)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_PACKAGE))
    return Path(env)


def get_bazel_workspace_root() -> Path:
    env = os.getenv("BUILD_WORKING_DIRECTORY")
    if not env:
        raise EnvironmentError("BUILD_WORKING_DIRECTORY is not set")
    return Path(env)


def get_ansible_args() -> List[str]:
    env = os.getenv(ENV_ANSIBLE_BZL_ARGS)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_ARGS))
    return json.loads(env)


def get_ansible_vault_files() -> List[str]:
    env = os.getenv(ENV_ANSIBLE_BZL_VAULT_FILES)
    if not env:
        raise EnvironmentError("{} is not set".format(ENV_ANSIBLE_BZL_ARGS))
    return json.loads(env)


def get_ansible_config(target_package_dir: Optional[Path] = None) -> Optional[Path]:
    if not target_package_dir:
        target_package_dir = get_target_package_dir()
    env = os.getenv(ENV_ANSIBLE_BZL_CONFIG)
    if not env:
        return None
    return target_package_dir / env


def find_vault_key() -> Optional[Path]:
    # This assumes inventories are structured as `./inventories/<environment>/hosts`.
    # So if the grand parent of the hosts file is not a directory named `inventories`,
    # we assume the vault pass directory is structured in the same way.
    hosts_file = get_inventory_hosts()
    if hosts_file.parent.parent.parent.name == "inventories":
        vault_pass_dir = Path(".vault_pass") / hosts_file.parent.parent
    else:
        vault_pass_dir = Path(".vault_pass")

    # First look in the package directory for vault key
    package_dir = get_bazel_workspace_root() / get_ansible_package()
    vault_key = package_dir / vault_pass_dir

    # Check the parent directory
    if not vault_key.exists():
        vault_key = package_dir.parent / vault_pass_dir

    # if the key doesn't exist, try the workspace root
    if not vault_key.exists():
        vault_key = get_bazel_workspace_root() / vault_pass_dir

    if vault_key.exists():
        return vault_key

    return None


def decrypt_keys(
    vault_dir: Path,
    vault_files: List[Path],
    vault_key: Optional[Path],
    clean: bool = False,
):

    command = [
        get_ansible_vault_bin(),
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

    suffix = ("." + os.environ.get(ENV_ANSIBLE_BZL_LAUNCHER_NAME, "")).rstrip(
        "."
    ) + ".vaultfile"

    for file in vault_dir.iterdir():
        if file.name not in vault_files:
            continue

        # Now make sure to "install" the files by stripping the `.vaultfile` extension
        decrypted_file = Path(str(file)[: -len(suffix)])

        vault_command = command + [
            str(file),
            "--output",
            str(decrypted_file),
        ]

        environ = os.environ.copy()

        subprocess.run(vault_command, check=False, env=environ)


def run_ansible(
    playbook: Path,
    vault_password_file: Optional[Path] = None,
    extra_args: List[str] = [],
) -> None:
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


def main():

    playbook = get_playbook()
    if not playbook.exists():
        raise FileNotFoundError("Requested playbook not found", playbook)

    # Check for an explicit vault key
    vault_key = find_vault_key()

    playbook_dir = playbook.parent
    vault_dir = playbook_dir / "vault"

    # Check for any vault files
    decrypt_keys(
        vault_files=get_ansible_vault_files(),
        vault_dir=vault_dir,
        vault_key=vault_key,
    )

    run_ansible(
        playbook_dir=playbook_dir,
        playbook=playbook,
        vault_password_file=vault_key,
        extra_args=get_ansible_args(),
    )


if __name__ == "__main__":
    main()
