"""Utility functions for rules_ansible"""

def py_binary_wrapper(ctx, binary, runfiles):
    """Generate an executable symlink for an existing py_binary target

    Because executable rules must produce the executable and there is no `py_common`
    API with which to produce `py_binary` equivilant targets ourselves. Another `py_binary`
    target is symlinked to be this rule's executable.

    https://github.com/bazelbuild/bazel/issues/15546

    Args:
        ctx (ctx): The rule's context object.
        binary (Target): The `py_binary` target.
        runfiles (runfiles): A runfiles object to add to.

    Returns:
        the executable and the updated runfiles.
    """

    orig_exe = binary[DefaultInfo].files_to_run.executable
    is_windows = orig_exe.extension == ".exe"
    executable = ctx.actions.declare_file(ctx.label.name + (".exe" if is_windows else ""))

    ctx.actions.symlink(
        output = executable,
        target_file = orig_exe,
        is_executable = True,
    )

    files = []

    # Windows requires the python_zip_file output of a py_binary
    if is_windows:
        zip_file = ctx.actions.declare_file(ctx.label.name + ".zip")
        python_zip_file = binary[OutputGroupInfo].python_zip_file.to_list()[0]
        ctx.actions.symlink(
            output = python_zip_file,
            target_file = zip_file,
            is_executable = True,
        )
        files.append(python_zip_file)

    runfiles = runfiles.merge(ctx.runfiles(
        files = files,
    ))

    runfiles = runfiles.merge(
        binary[DefaultInfo].default_runfiles,
    )

    return executable, runfiles
