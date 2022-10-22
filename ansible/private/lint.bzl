"""Rules for linting ansible playbooks"""

load("//ansible/private/utils:utils.bzl", "py_binary_wrapper")
load(":ansible.bzl", "AnsiblePlaybookInfo")

def _ansible_lint_aspect_impl(target, ctx):
    if AnsiblePlaybookInfo not in target:
        return []

    playbook_info = target[AnsiblePlaybookInfo]

    args = ctx.actions.args()

    inputs = depset(
        [playbook_info.playbook, ctx.file._config],
        transitive = [playbook_info.inventory, playbook_info.roles],
    )

    output = ctx.actions.declare_file(target.label.name + ".ansible_lint_check")

    args.add("--output", output)
    args.add("--playbook", target[AnsiblePlaybookInfo].playbook)
    args.add("--config_file", ctx.file._config)
    args.add("--")
    args.add("--show-relpath")
    args.add("--offline")

    ctx.actions.run(
        executable = ctx.executable._process_wrapper,
        inputs = inputs,
        outputs = [output],
        arguments = [args],
        mnemonic = "AnsibleLint",
        progress_message = "Ansible linting {}".format(target.label),
    )

    return [OutputGroupInfo(
        ansible_lint_checks = depset([output]),
    )]

ansible_lint_aspect = aspect(
    implementation = _ansible_lint_aspect_impl,
    doc = "An aspect for linting ansible targets.",
    attrs = {
        "_config": attr.label(
            doc = "The ansible config-lint file to use",
            default = Label("//ansible:lint_config"),
            allow_single_file = True,
        ),
        "_process_wrapper": attr.label(
            doc = "A process wrapper for running `ansible-lint`.",
            cfg = "exec",
            executable = True,
            default = Label("//ansible/private:ansible_lint_process_wrapper"),
        ),
    },
)

def _ansible_lint_test_impl(ctx):
    playbook_info = ctx.attr.playbook[AnsiblePlaybookInfo]

    args = []
    args.extend(["--playbook", playbook_info.playbook.short_path])
    args.extend(["--config_file", ctx.file.config.short_path])
    args.append("--")
    args.append("--show-relpath")
    args.append("--offline")

    args_file = ctx.actions.declare_file("{}.args_file")
    ctx.actions.write(
        output = args_file,
        content = "\n".join(args),
    )

    runfiles = ctx.runfiles(
        files = [args_file, playbook_info.playbook, playbook_info.hosts, ctx.file.config],
        transitive_files = depset(transitive = [playbook_info.inventory, playbook_info.roles]),
    )

    runner, runfiles = py_binary_wrapper(ctx, ctx.attr._process_wrapper, runfiles)

    return [
        DefaultInfo(
            files = depset([runner]),
            runfiles = runfiles,
            executable = runner,
        ),
        testing.TestEnvironment(
            environment = {
                "ANSIBLE_LINT_ARGS_FILE": args_file.short_path,
            },
        ),
    ]

ansible_lint_test = rule(
    implementation = _ansible_lint_test_impl,
    doc = "A test rule for running `ansible-lint` on an Ansible playbook.",
    attrs = {
        "config": attr.label(
            doc = "The ansible-lint config file to use",
            default = Label("//ansible:lint_config"),
            allow_single_file = True,
        ),
        "playbook": attr.label(
            doc = "The `ansible_playbook` target to lint.",
            providers = [AnsiblePlaybookInfo],
            mandatory = True,
        ),
        "_process_wrapper": attr.label(
            doc = "A process wrapper for running `ansible-lint`.",
            cfg = "exec",
            executable = True,
            default = Label("//ansible/private:ansible_lint_process_wrapper"),
        ),
    },
    test = True,
)
