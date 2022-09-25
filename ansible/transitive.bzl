"""Ansible transitive dependencies"""

load("@rules_python//python:repositories.bzl", "python_register_toolchains")

def rules_ansible_transitive_dependencies():
    python_register_toolchains(
        name = "python39",
        python_version = "3.9",
    )
