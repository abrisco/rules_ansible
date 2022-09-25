"""Ansible pip dependencies"""

load("@python39//:defs.bzl", "interpreter")
load("@rules_python//python:pip.bzl", "pip_parse")

def rules_ansible_pip_dependencies():
    pip_parse(
        name = "rules_ansible.pip",
        requirements_lock = Label("//ansible:requirements.txt"),
        python_interpreter_target = interpreter,
    )
