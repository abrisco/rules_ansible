"""Ansible toolchain definitions"""

load("@rules_venv//python:py_info.bzl", "PyInfo")

def _ansible_toolchain_impl(ctx):
    return platform_common.ToolchainInfo(
        ansible = ctx.attr.ansible,
        ansible_core = ctx.attr.ansible_core,
        ansible_lint = ctx.attr.ansible_lint,
    )

ansible_toolchain = rule(
    implementation = _ansible_toolchain_impl,
    doc = "An ansible toolchain",
    attrs = {
        "ansible": attr.label(
            doc = "An [ansible](https://pypi.org/project/ansible/) `py_library` target.",
            mandatory = True,
            providers = [PyInfo],
        ),
        "ansible_core": attr.label(
            doc = "An [ansible-core](https://pypi.org/project/ansible-core/) `py_library` target.",
            mandatory = True,
            providers = [PyInfo],
        ),
        "ansible_lint": attr.label(
            doc = "An [ansible-lint](https://pypi.org/project/ansible-lint/) `py_library` target.",
            mandatory = True,
            providers = [PyInfo],
        ),
    },
)

def _current_ansible_toolchain_impl(ctx):
    toolchain = ctx.toolchains[Label("//ansible:toolchain_type")]

    if ctx.attr.lib == "ansible":
        target = toolchain.ansible
    elif ctx.attr.lib == "ansible_core":
        target = toolchain.ansible_core
    elif ctx.attr.lib == "ansible_lint":
        target = toolchain.ansible_lint
    else:
        fail("Unexpected lib type: {}".format(ctx.attr.lib))

    # TODO: Due to a bug in Bazel, DefaultInfo needs to be recreated.
    default_info = DefaultInfo(
        files = target[DefaultInfo].files,
        runfiles = ctx.runfiles(files = target[DefaultInfo].default_runfiles.files.to_list()),
    )

    return [
        default_info,
        target[InstrumentedFilesInfo],
        target[OutputGroupInfo],
        target[PyInfo],
    ]

current_ansible_toolchain = rule(
    implementation = _current_ansible_toolchain_impl,
    toolchains = [str(Label("//ansible:toolchain_type"))],
    attrs = {
        "lib": attr.string(
            doc = "Which py_library within the ansible toolchain to yield providers from",
            values = [
                "ansible",
                "ansible_core",
                "ansible_lint",
            ],
            default = "ansible",
        ),
    },
)
