from os import path

from kubetools.constants import (
    GIT_BRANCH_ANNOTATION_KEY,
    GIT_COMMIT_ANNOTATION_KEY,
    GIT_TAG_ANNOTATION_KEY,
)
from kubetools.deploy.util import run_shell_command
from kubetools.exceptions import KubeBuildError


def _is_git_committed(app_dir):
    git_status = run_shell_command(
        'git', 'status', '--porcelain',
        cwd=app_dir,
    ).strip().decode()

    if git_status:
        return False
    return True


def _get_git_info(app_dir):
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


def get_git_info(app_dir, ignore_git_changes=False):
    if path.exists(path.join(app_dir, '.git')):
        if not _is_git_committed(app_dir) and not ignore_git_changes:
            raise KubeBuildError(f'{app_dir} contains uncommitted changes, refusing to deploy!')
        return _get_git_info(app_dir)
    raise KubeBuildError(f'{app_dir} is not a valid git repository!')
