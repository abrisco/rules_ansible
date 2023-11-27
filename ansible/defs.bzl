"""# rules_ansible

Bazel rules for running [Ansible playbooks](https://docs.ansible.com/ansible/latest/user_guide/playbooks_intro.html)

## Setup

```starlark
load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

# See releases for urls and checksums
http_archive(
    name = "rules_ansible",
    sha256 = "{sha256}",
    urls = ["https://github.com/abrisco/rules_ansible/releases/download/{version}/rules_ansible-v{version}.tar.gz"],
)

load("@rules_ansible//ansible:repositories.bzl", "rules_ansible_dependencies")

rules_ansible_dependencies()
```

### Registering toolchains

The rules provide sufficient python requirements for running Ansible. To load these requirements, use the following
snippet.

```starlark
load("@rules_ansible//ansible:transitive.bzl", "rules_ansible_transitive_dependencies")

rules_ansible_transitive_dependencies()

load("@rules_ansible//ansible:pip_deps.bzl", "rules_ansible_pip_dependencies")

rules_ansible_pip_dependencies()

load("@rules_ansible//ansible:pip_deps_install.bzl", "rules_ansible_pip_dependencies_install")

rules_ansible_pip_dependencies_install()

load("@rules_ansible//ansible:repositories.bzl", "ansible_register_toolchains")

ansible_register_toolchains()
```

However, if users whish to control the version of Ansible being used, they can create a custom [ansible_toolchain](#ansible_toolchain)
with their own requirements and register that in the workspace.

## Rules

- [ansible_lint_aspect](#ansible_lint_aspect)
- [ansible_lint_test](#ansible_lint_test)
- [ansible_playbook](#ansible_playbook)
- [ansible_toolchain](#ansible_toolchain)
- [current_ansible_toolchain](#current_ansible_toolchain)

---
---

"""

load(
    "//private:ansible.bzl",
    _ansible_playbook = "ansible_playbook",
)
load(
    "//private:lint.bzl",
    _ansible_lint_aspect = "ansible_lint_aspect",
    _ansible_lint_test = "ansible_lint_test",
)
load(
    ":repositories.bzl",
    _ansible_register_toolchains = "ansible_register_toolchains",
    _rules_ansible_dependencies = "rules_ansible_dependencies",
)
load(
    ":toolchain.bzl",
    _ansible_toolchain = "ansible_toolchain",
    _current_ansible_toolchain = "current_ansible_toolchain",
)

ansible_lint_aspect = _ansible_lint_aspect
ansible_lint_test = _ansible_lint_test
ansible_playbook = _ansible_playbook
ansible_register_toolchains = _ansible_register_toolchains
ansible_toolchain = _ansible_toolchain
current_ansible_toolchain = _current_ansible_toolchain
rules_ansible_dependencies = _rules_ansible_dependencies
