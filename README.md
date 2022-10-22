<!-- Generated with Stardoc: http://skydoc.bazel.build -->

# rules_ansible

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



<a id="ansible_lint_test"></a>

## ansible_lint_test

<pre>
ansible_lint_test(<a href="#ansible_lint_test-name">name</a>, <a href="#ansible_lint_test-config">config</a>, <a href="#ansible_lint_test-playbook">playbook</a>)
</pre>

A test rule for running `ansible-lint` on an Ansible playbook.

**ATTRIBUTES**


| Name  | Description | Type | Mandatory | Default |
| :------------- | :------------- | :------------- | :------------- | :------------- |
| <a id="ansible_lint_test-name"></a>name |  A unique name for this target.   | <a href="https://bazel.build/concepts/labels#target-names">Name</a> | required |  |
| <a id="ansible_lint_test-config"></a>config |  The ansible-lint config file to use   | <a href="https://bazel.build/concepts/labels">Label</a> | optional | //ansible:lint_config |
| <a id="ansible_lint_test-playbook"></a>playbook |  The <code>ansible_playbook</code> target to lint.   | <a href="https://bazel.build/concepts/labels">Label</a> | required |  |


<a id="ansible_playbook"></a>

## ansible_playbook

<pre>
ansible_playbook(<a href="#ansible_playbook-name">name</a>, <a href="#ansible_playbook-config">config</a>, <a href="#ansible_playbook-inventory">inventory</a>, <a href="#ansible_playbook-playbook">playbook</a>, <a href="#ansible_playbook-roles">roles</a>, <a href="#ansible_playbook-vault">vault</a>)
</pre>

A rule for running [Ansible playbooks](https://docs.ansible.com/ansible/latest/user_guide/playbooks_intro.html)

**ATTRIBUTES**


| Name  | Description | Type | Mandatory | Default |
| :------------- | :------------- | :------------- | :------------- | :------------- |
| <a id="ansible_playbook-name"></a>name |  A unique name for this target.   | <a href="https://bazel.build/concepts/labels#target-names">Name</a> | required |  |
| <a id="ansible_playbook-config"></a>config |  The path to an Ansible config file.   | <a href="https://bazel.build/concepts/labels">Label</a> | optional | //ansible:config |
| <a id="ansible_playbook-inventory"></a>inventory |  Ansible inventory files   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional | [] |
| <a id="ansible_playbook-playbook"></a>playbook |  The ansible playbook yaml file.   | <a href="https://bazel.build/concepts/labels">Label</a> | required |  |
| <a id="ansible_playbook-roles"></a>roles |  The source files for all ansible roles required by the playbook.   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional | [] |
| <a id="ansible_playbook-vault"></a>vault |  Vautl files to be decrypted before running   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional | [] |


<a id="ansible_toolchain"></a>

## ansible_toolchain

<pre>
ansible_toolchain(<a href="#ansible_toolchain-name">name</a>, <a href="#ansible_toolchain-ansible">ansible</a>, <a href="#ansible_toolchain-ansible_core">ansible_core</a>, <a href="#ansible_toolchain-ansible_lint">ansible_lint</a>)
</pre>

An ansible toolchain

**ATTRIBUTES**


| Name  | Description | Type | Mandatory | Default |
| :------------- | :------------- | :------------- | :------------- | :------------- |
| <a id="ansible_toolchain-name"></a>name |  A unique name for this target.   | <a href="https://bazel.build/concepts/labels#target-names">Name</a> | required |  |
| <a id="ansible_toolchain-ansible"></a>ansible |  An [ansible](https://pypi.org/project/ansible/) <code>py_library</code> target.   | <a href="https://bazel.build/concepts/labels">Label</a> | required |  |
| <a id="ansible_toolchain-ansible_core"></a>ansible_core |  An [ansible-core](https://pypi.org/project/ansible-core/) <code>py_library</code> target.   | <a href="https://bazel.build/concepts/labels">Label</a> | required |  |
| <a id="ansible_toolchain-ansible_lint"></a>ansible_lint |  An [ansible-lint](https://pypi.org/project/ansible-lint/) <code>py_library</code> target.   | <a href="https://bazel.build/concepts/labels">Label</a> | required |  |


<a id="current_ansible_toolchain"></a>

## current_ansible_toolchain

<pre>
current_ansible_toolchain(<a href="#current_ansible_toolchain-name">name</a>, <a href="#current_ansible_toolchain-lib">lib</a>)
</pre>



**ATTRIBUTES**


| Name  | Description | Type | Mandatory | Default |
| :------------- | :------------- | :------------- | :------------- | :------------- |
| <a id="current_ansible_toolchain-name"></a>name |  A unique name for this target.   | <a href="https://bazel.build/concepts/labels#target-names">Name</a> | required |  |
| <a id="current_ansible_toolchain-lib"></a>lib |  Which py_library within the ansible toolchain to yield providers from   | String | optional | "ansible" |


<a id="ansible_register_toolchains"></a>

## ansible_register_toolchains

<pre>
ansible_register_toolchains(<a href="#ansible_register_toolchains-register_toolchains">register_toolchains</a>)
</pre>



**PARAMETERS**


| Name  | Description | Default Value |
| :------------- | :------------- | :------------- |
| <a id="ansible_register_toolchains-register_toolchains"></a>register_toolchains |  <p align="center"> - </p>   |  <code>True</code> |


<a id="rules_ansible_dependencies"></a>

## rules_ansible_dependencies

<pre>
rules_ansible_dependencies()
</pre>





<a id="ansible_lint_aspect"></a>

## ansible_lint_aspect

<pre>
ansible_lint_aspect(<a href="#ansible_lint_aspect-name">name</a>)
</pre>

An aspect for linting ansible targets.

**ASPECT ATTRIBUTES**



**ATTRIBUTES**


| Name  | Description | Type | Mandatory | Default |
| :------------- | :------------- | :------------- | :------------- | :------------- |
| <a id="ansible_lint_aspect-name"></a>name |  A unique name for this target.   | <a href="https://bazel.build/concepts/labels#target-names">Name</a> | required |   |


