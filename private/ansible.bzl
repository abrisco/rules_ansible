"""Ansible rules"""

load("@rules_venv//python/venv:defs.bzl", "py_venv_common")
load(
    "//private/utils:utils.bzl",
    "ansible_script_main_finder_aspect",
    "generate_process_wrapper",
    "get_process_wrapper_attr",
)

AnsiblePlaybookInfo = provider(
    doc = "Infomation describing components of an Ansible playbook.",
    fields = {
        "hosts": "File: The hosts file for the current inventory",
        "inventory": "depset[File]: The sources of all inventory files",
        "playbook": "File: The root of the playbook",
        "roles": "depset[File]: The sources of all roles for the playbook",
    },
)

def _label_relativize(file):
    """A utility function for determining the path of a file relative to the package it's defined in.

    Args:
        file (File): The file in question.

    Returns:
        str: The file path relative to the owner's package.
    """
    repo_path = file.short_path
    if repo_path.startswith("../"):
        repo_path = repo_path[3:]

    if repo_path.startswith(file.owner.package):
        repo_path = repo_path[len(file.owner.package):].lstrip("/")

    return repo_path

def _copy_arg(file, is_windows):
    if is_windows:
        return file.path.replace("/", "\\")
    return file.path

def _vault_copy_action(ctx, file):
    """Spawn an action to copy a vault file.

    Vault files are intended to be un-remote cachable.

    Args:
        ctx (ctx): The rule's context object.
        file (File): A file in question.

    Returns:
        File: The action output.
    """
    copy = ctx.actions.declare_file("{}.ansible/{}.vaultfile".format(
        ctx.label.name,
        _label_relativize(file),
    ))
    is_windows = ctx.executable._copier.basename.endswith((".bat", ".exe", ".ps1"))
    args = ctx.actions.args()
    args.add(_copy_arg(file, is_windows))
    args.add(_copy_arg(copy, is_windows))
    ctx.actions.run(
        executable = ctx.executable._copier,
        mnemonic = "AnsibleVaultCopier",
        outputs = [copy],
        arguments = [args],
        inputs = [file],
        # Rationale for the execution requirements can be found here:
        # https://github.com/bazelbuild/bazel-skylib/blob/1.8.1/rules/private/copy_common.bzl#L18-L45
        execution_requirements = {
            "no-cache": "1",
            "no-remote": "1",
        },
    )
    return copy

def _copy_action(ctx, file, name = None):
    """Spawn an action to copy a file.

    Args:
        ctx (ctx): The rule's context object.
        file (File): A file in question.
        name (str, optional): If set, this will be the path to the file instead of it's
            package relativie name.

    Returns:
        File: The action output.
    """
    output = ctx.actions.declare_file("{}.ansible/{}".format(
        ctx.label.name,
        name or _label_relativize(file),
    ))
    is_windows = ctx.executable._copier.basename.endswith((".bat", ".exe", ".ps1"))
    args = ctx.actions.args()
    args.add(_copy_arg(file, is_windows))
    args.add(_copy_arg(output, is_windows))
    ctx.actions.run(
        executable = ctx.executable._copier,
        mnemonic = "AnsibleCopier",
        outputs = [output],
        arguments = [args],
        inputs = [file],
        # Rationale for the execution requirements can be found here:
        # https://github.com/bazelbuild/bazel-skylib/blob/1.8.1/rules/private/copy_common.bzl#L18-L45
        execution_requirements = {
            "no-cache": "1",
            "no-remote": "1",
        },
        use_default_shell_env = True,
    )

    return output

def _copy_inventory_action(ctx, file):
    """Spawn an action to copy an inventory file.

    This function accounts for inventory structures where the targets
    representing the inventory files may be within the `inventories`
    directory. E.g. `//infra/ansible/inventories/staging:inventory`.

    Args:
        ctx (ctx): The rule's context object.
        file (File): A file in question.

    Returns:
        File: The action output.
    """
    name = file.basename
    if "inventories" in file.owner.package:
        _, _, env = file.owner.package.partition("inventories")
        file_path = _label_relativize(file)
        name = "inventories/{}/{}".format(env, file_path)

    return _copy_action(ctx, file, name)

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _ansible_playbook_impl(ctx):
    venv_toolchain = py_venv_common.get_toolchain(ctx)
    hosts_file = _copy_inventory_action(ctx, ctx.file.hosts)
    inventory_files = [_copy_inventory_action(ctx, file) for file in ctx.files.inventory]
    role_files = [_copy_action(ctx, file) for file in ctx.files.roles]
    playbook = _copy_action(ctx, ctx.file.playbook)
    config = _copy_action(ctx, ctx.file.config)

    # Create copies of all vault files to allow for them to be decrypted at
    # runtime without ever litering the repo with decrypted files
    vault_files = [_vault_copy_action(ctx, file) for file in ctx.files.vault]

    env = {
        "ANSIBLE_BZL_ARGS": json.encode(getattr(ctx.attr, "args", [])),
        "ANSIBLE_BZL_CONFIG": _rlocationpath(config, ctx.workspace_name),
        "ANSIBLE_BZL_INVENTORY_HOSTS": _rlocationpath(hosts_file, ctx.workspace_name),
        "ANSIBLE_BZL_LAUNCHER_NAME": ctx.label.name,
        "ANSIBLE_BZL_PACKAGE": ctx.label.package,
        "ANSIBLE_BZL_PLAYBOOK": _rlocationpath(playbook, ctx.workspace_name),
        "ANSIBLE_BZL_VAULT_FILES": json.encode([_rlocationpath(file, ctx.workspace_name) for file in vault_files]),
    }

    data = [playbook, config, hosts_file] + vault_files + inventory_files + role_files

    script_info = get_process_wrapper_attr(ctx, "_launcher")

    runner, runfiles = generate_process_wrapper(
        ctx = ctx,
        script_info = script_info,
        runfiles = ctx.runfiles(files = data, transitive_files = venv_toolchain.all_files),
    )

    return [
        AnsiblePlaybookInfo(
            playbook = playbook,
            hosts = hosts_file,
            inventory = depset(inventory_files + [hosts_file]),
            roles = depset(role_files),
        ),
        DefaultInfo(
            files = depset([runner]),
            runfiles = runfiles,
            executable = runner,
        ),
        RunEnvironmentInfo(
            environment = env,
        ),
    ]

ansible_playbook = rule(
    implementation = _ansible_playbook_impl,
    doc = "A rule for running [Ansible playbooks](https://docs.ansible.com/ansible/latest/user_guide/playbooks_intro.html)",
    attrs = {
        "config": attr.label(
            doc = "The path to an Ansible config file.",
            default = Label("//ansible:config"),
            allow_single_file = True,
        ),
        "hosts": attr.label(
            doc = "Ansible hosts file",
            allow_single_file = True,
            mandatory = True,
        ),
        "inventory": attr.label_list(
            doc = "Ansible inventory files",
            allow_files = True,
        ),
        "playbook": attr.label(
            doc = "The ansible playbook yaml file.",
            allow_single_file = True,
            mandatory = True,
        ),
        "roles": attr.label_list(
            doc = "The source files for all ansible roles required by the playbook.",
            allow_files = True,
        ),
        "vault": attr.label_list(
            doc = "Vault files to be decrypted before running",
            allow_files = True,
        ),
        "_copier": attr.label(
            doc = "A utility binary for copying vault files.",
            cfg = "exec",
            executable = True,
            default = Label("//private/utils:copier"),
        ),
        "_launcher": attr.label(
            doc = "The process wrapper for launching `ansible-playbook`",
            cfg = "target",
            executable = True,
            aspects = [ansible_script_main_finder_aspect],
            default = Label("//private:ansible_launcher"),
        ),
    } | py_venv_common.create_venv_attrs(),
    executable = True,
    toolchains = [
        py_venv_common.TOOLCHAIN_TYPE,
    ],
)
