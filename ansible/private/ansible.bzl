"""Ansible rules"""

load("//ansible/private/utils:utils.bzl", "py_binary_wrapper")

AnsiblePlaybookInfo = provider(
    doc = "Infomation describing components of an Ansible playbook.",
    fields = {
        "hosts": "File: The hosts file for the current inventory",
        "inventory": "depset[File]: The sources of all inventory files",
        "playbook": "File: The root of the playbook",
        "roles": "depset[File]: The sources of all roles for the playbook",
    },
)

def _ansible_impl(ctx):
    # Create copies of all vault files to allow for them to be decrypted at
    # runtime without ever litering the repo with decrypted files
    vault_files = []
    for vault_file in ctx.files.vault:
        copy = ctx.actions.declare_file("{}.{}.vaultfile".format(
            vault_file.owner.name,
            ctx.label.name,
        ))
        args = ctx.actions.args()
        args.add("--source", vault_file)
        args.add("--destination", copy)
        ctx.actions.run(
            executable = ctx.executable._copier,
            mnemonic = "AnsibleVaultCopier",
            outputs = [copy],
            arguments = [args],
            inputs = [vault_file],
            execution_requirements = {
                "no-remote-cache": "1",
            },
        )
        vault_files.append(copy)

    hosts_files = []
    for src in ctx.files.inventory:
        if src.basename == "hosts":
            hosts_files.append(src)

    if len(hosts_files) != 1:
        fail("Ansible playbooks are expected to have 1 hosts file available. Instead {} contained {}".format(
            ctx.label,
            hosts_files,
        ))

    hosts_file = hosts_files[0]

    env = {
        "ANSIBLE_BZL_ARGS": json.encode(getattr(ctx.attr, "args", [])),
        "ANSIBLE_BZL_CONFIG": ctx.file.config.short_path,
        "ANSIBLE_BZL_INVENTORY_HOSTS": hosts_file.short_path,
        "ANSIBLE_BZL_LAUNCHER_NAME": ctx.label.name,
        "ANSIBLE_BZL_PACKAGE": ctx.label.package,
        "ANSIBLE_BZL_PLAYBOOK": ctx.file.playbook.short_path,
        "ANSIBLE_BZL_VAULT_FILES": json.encode([file.short_path for file in vault_files]),
        "ANSIBLE_BZL_WORKSPACE_NAME": ctx.workspace_name,
    }

    data = [ctx.file.playbook, ctx.file.config] + vault_files + ctx.files.inventory + ctx.files.roles

    runner, runfiles = py_binary_wrapper(ctx, ctx.attr._launcher, ctx.runfiles(files = data))

    return [
        AnsiblePlaybookInfo(
            playbook = ctx.file.playbook,
            hosts = hosts_file,
            inventory = depset(ctx.files.inventory),
            roles = depset(ctx.files.roles),
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
    implementation = _ansible_impl,
    doc = "A rule for running [Ansible playbooks](https://docs.ansible.com/ansible/latest/user_guide/playbooks_intro.html)",
    attrs = {
        "config": attr.label(
            doc = "The path to an Ansible config file.",
            default = Label("//ansible:config"),
            allow_single_file = True,
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
            doc = "Vautl files to be decrypted before running",
            allow_files = True,
        ),
        "_copier": attr.label(
            doc = "A utility binary for copying vault files.",
            cfg = "exec",
            executable = True,
            default = Label("//ansible/private/utils:copier"),
        ),
        "_launcher": attr.label(
            doc = "The process wrapper for launching `ansible-playbook`",
            cfg = "target",
            executable = True,
            default = Label("//ansible/private:ansible_launcher"),
        ),
    },
    executable = True,
)
