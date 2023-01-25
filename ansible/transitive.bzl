"""Ansible transitive dependencies"""

load("@rules_python//python:repositories.bzl", "py_repositories", "python_register_toolchains")

def rules_ansible_transitive_dependencies():
    py_repositories()

    python_register_toolchains(
        name = "python311",
        python_version = "3.11",
    )
