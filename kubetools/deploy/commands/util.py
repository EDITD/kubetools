from kubetools.constants import (
    GIT_BRANCH_ANNOTATION_KEY,
    GIT_COMMIT_ANNOTATION_KEY,
    GIT_TAG_ANNOTATION_KEY,
)
from kubetools.deploy.util import run_shell_command
from kubetools.exceptions import KubeBuildError


def is_git_committed(app_dir):
    git_status = run_shell_command(
        'git', 'status', '--porcelain',
        cwd=app_dir,
    ).strip().decode()

    if git_status:
        return False
    return True


def get_git_info(app_dir):
    git_annotations = {}

    commit_hash = run_shell_command(
        'git', 'rev-parse', '--short=7', 'HEAD',
        cwd=app_dir,
    ).strip().decode()
    git_annotations[GIT_COMMIT_ANNOTATION_KEY] = commit_hash

    branch_name = run_shell_command(
        'git', 'rev-parse', '--abbrev-ref', 'HEAD',
        cwd=app_dir,
    ).strip().decode()

    if branch_name != 'HEAD':
        git_annotations[GIT_BRANCH_ANNOTATION_KEY] = branch_name

    try:
        git_tag = run_shell_command(
            'git', 'tag', '--points-at', commit_hash,
            cwd=app_dir,
        ).strip().decode()
    except KubeBuildError:
        pass
    else:
        if git_tag:
            git_annotations[GIT_TAG_ANNOTATION_KEY] = git_tag

    return commit_hash, git_annotations
