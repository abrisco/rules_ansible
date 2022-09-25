"""Dependencies of Ansible pip dependencies"""

load("@rules_ansible.pip//:requirements.bzl", "install_deps")

def rules_ansible_pip_dependencies_install():
    install_deps()
