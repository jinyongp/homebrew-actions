#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZE = ROOT / "internal" / "policy" / "authorize-update.py"
RECONCILE = ROOT / "internal" / "policy" / "reconcile.sh"

APPROVED_SHA = "a" * 40
OLD_SHA = "b" * 40
APPROVED_TAG = "v1.2.0"
OLD_TAG = "v1.1.0"

CHECK = "jinyongp/homebrew-actions/.github/workflows/check.yml"
PUBLISH = "jinyongp/homebrew-actions/.github/workflows/publish.yml"
POLICY = "jinyongp/homebrew-actions/.github/workflows/update-policy.yml"

HEAD_WORKFLOWS = {
    "ci.yml": (
        "jobs:\n"
        f"  homebrew:\n    uses: {CHECK}@{APPROVED_SHA} # {APPROVED_TAG}\n"
    ),
    "release.yml": (
        "jobs:\n"
        f"  homebrew:\n    uses: {PUBLISH}@{APPROVED_SHA} # {APPROVED_TAG}\n"
    ),
    "homebrew-policy.yml": (
        "jobs:\n"
        f"  policy:\n    uses: {POLICY}@{APPROVED_SHA} # {APPROVED_TAG}\n"
    ),
}

DEPENDENCY_FILE = {
    CHECK: ".github/workflows/ci.yml",
    PUBLISH: ".github/workflows/release.yml",
    POLICY: ".github/workflows/homebrew-policy.yml",
}

DEPENDENCY_WORKFLOW = {
    CHECK: "ci.yml",
    PUBLISH: "release.yml",
    POLICY: "homebrew-policy.yml",
}

DEPENDABOT_COMMIT = {
    "author": {"login": "dependabot[bot]"},
    "commit": {"verification": {"verified": True}},
}


def base_workflows_for(changed):
    changed = set(changed)
    result = {}
    for dependency, filename in DEPENDENCY_WORKFLOW.items():
        contents = HEAD_WORKFLOWS[filename]
        if dependency in changed:
            contents = (
                contents
                .replace(APPROVED_SHA, OLD_SHA)
                .replace(APPROVED_TAG, OLD_TAG)
            )
        result[filename] = contents
    return result


def changed_files_for(changed):
    files = []
    for dependency in changed:
        files.append({
            "filename": DEPENDENCY_FILE[dependency],
            "status": "modified",
            "patch": (
                "@@ -1 +1 @@\n"
                f"-    uses: {dependency}@{OLD_SHA} # {OLD_TAG}\n"
                f"+    uses: {dependency}@{APPROVED_SHA} # {APPROVED_TAG}"
            ),
        })
    return files


def authorized(
    *,
    changed=(CHECK, PUBLISH, POLICY),
    commits=None,
    files=None,
    base_workflows=None,
    head_workflows=None,
    expected_commit_count=None,
    expected_file_count=None,
    approved_sha=APPROVED_SHA,
    approved_tag=APPROVED_TAG,
):
    commits = [DEPENDABOT_COMMIT] if commits is None else commits
    files = changed_files_for(changed) if files is None else files
    base_workflows = base_workflows_for(changed) if base_workflows is None else base_workflows
    head_workflows = HEAD_WORKFLOWS if head_workflows is None else head_workflows
    expected_commit_count = len(commits) if expected_commit_count is None else expected_commit_count
    expected_file_count = len(files) if expected_file_count is None else expected_file_count

    with tempfile.TemporaryDirectory() as directory:
        evidence = Path(directory)
        commits_path = evidence / "commits.json"
        files_path = evidence / "files.json"
        base = evidence / "base"
        head = evidence / "head"
        base.mkdir()
        head.mkdir()
        commits_path.write_text(json.dumps(commits))
        files_path.write_text(json.dumps(files))
        for name, contents in base_workflows.items():
            (base / name).write_text(contents)
        for name, contents in head_workflows.items():
            (head / name).write_text(contents)

        return subprocess.run(
            [
                "python3",
                str(AUTHORIZE),
                "--commits", str(commits_path),
                "--files", str(files_path),
                "--expected-commit-count", str(expected_commit_count),
                "--expected-file-count", str(expected_file_count),
                "--approved-sha", approved_sha,
                "--approved-tag", approved_tag,
                "--base-workflows", str(base),
                "--head-workflows", str(head),
            ],
            text=True,
            capture_output=True,
            check=False,
        )


def assert_authorization() -> None:
    for changed in [
        (CHECK,),
        (PUBLISH,),
        (POLICY,),
        (CHECK, PUBLISH, POLICY),
    ]:
        result = authorized(changed=changed)
        assert result.returncode == 0, result.stderr

    result = authorized(
        changed=(),
        files=changed_files_for((CHECK,)),
        expected_file_count=1,
    )
    assert result.returncode != 0
    assert "no homebrew-actions dependency update" in result.stderr

    result = authorized(commits=[{
        **DEPENDABOT_COMMIT,
        "author": {"login": "maintainer"},
    }])
    assert result.returncode != 0
    assert "authored and verified by Dependabot" in result.stderr

    result = authorized(commits=[{
        **DEPENDABOT_COMMIT,
        "commit": {"verification": {"verified": False}},
    }])
    assert result.returncode != 0

    result = authorized(expected_commit_count=2)
    assert result.returncode != 0

    result = authorized(
        changed=(CHECK,),
        files=[
            *changed_files_for((CHECK,)),
            {
                "filename": "README.md",
                "status": "modified",
                "patch": "@@ -1 +1 @@\n-old\n+new",
            },
        ],
        expected_file_count=2,
    )
    assert result.returncode != 0
    assert "unsupported file" in result.stderr

    changed_content = {
        **HEAD_WORKFLOWS,
        "ci.yml": HEAD_WORKFLOWS["ci.yml"] + "    timeout-minutes: 20\n",
    }
    result = authorized(changed=(CHECK,), head_workflows=changed_content)
    assert result.returncode != 0
    assert "content changed beyond" in result.stderr

    mismatched_sha = {
        **HEAD_WORKFLOWS,
        "release.yml": HEAD_WORKFLOWS["release.yml"].replace(APPROVED_SHA, "c" * 40),
    }
    result = authorized(head_workflows=mismatched_sha)
    assert result.returncode != 0
    assert "same commit SHA" in result.stderr

    branch_ref = {
        **HEAD_WORKFLOWS,
        "ci.yml": HEAD_WORKFLOWS["ci.yml"].replace(APPROVED_SHA, "main"),
    }
    result = authorized(head_workflows=branch_ref)
    assert result.returncode != 0
    assert "full commit SHA" in result.stderr

    wrong_comment = {
        **HEAD_WORKFLOWS,
        "ci.yml": HEAD_WORKFLOWS["ci.yml"].replace(APPROVED_TAG, "v9.9.9"),
    }
    result = authorized(head_workflows=wrong_comment)
    assert result.returncode != 0
    assert "same release comment" in result.stderr

    no_comment = {
        **HEAD_WORKFLOWS,
        "ci.yml": HEAD_WORKFLOWS["ci.yml"].replace(f" # {APPROVED_TAG}", ""),
    }
    result = authorized(head_workflows=no_comment)
    assert result.returncode != 0
    assert "adjacent vX.Y.Z comment" in result.stderr

    result = authorized(approved_sha="c" * 40)
    assert result.returncode != 0
    assert "latest immutable release SHA" in result.stderr

    result = authorized(approved_tag="v9.9.9")
    assert result.returncode != 0
    assert "latest immutable release" in result.stderr


FAKE_GH = r"""#!/bin/sh
set -eu
log="${FAKE_GH_LOG:?}"

case "$1 $2" in
  "pr view")
    printf '%s\n' "${FAKE_AUTO_MERGE_ENABLED:-true}"
    ;;
  "pr merge")
    shift 2
    if [ "${1:-}" = "--disable-auto" ]; then
      echo disable >> "$log"
      exit 0
    fi
    echo enable >> "$log"
    [ "${FAKE_ENABLE_FAIL:-false}" != "true" ] || exit 1
    ;;
  *)
    echo "unexpected gh command: $*" >&2
    exit 1
    ;;
esac
"""


def reconcile(outcome: str, *, enable_fail=False, auto_merge=True):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        fake_bin = path / "bin"
        fake_bin.mkdir()
        gh = fake_bin / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        output = path / "output"
        output.write_text("")
        log = path / "log"
        log.write_text("")

        env = dict(os.environ)
        env.update({
            "PATH": str(fake_bin) + os.pathsep + env["PATH"],
            "AUTHORIZATION_OUTCOME": outcome,
            "GITHUB_OUTPUT": str(output),
            "GH_TOKEN": "test-token",
            "PR_HEAD_SHA": "d" * 40,
            "PR_URL": "https://example.invalid/pull/1",
            "FAKE_GH_LOG": str(log),
            "FAKE_ENABLE_FAIL": "true" if enable_fail else "false",
            "FAKE_AUTO_MERGE_ENABLED": "true" if auto_merge else "false",
        })
        result = subprocess.run(
            ["bash", str(RECONCILE)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return result, output.read_text(), log.read_text()


def assert_reconcile() -> None:
    result, output, log = reconcile("success")
    assert result.returncode == 0, result.stderr
    assert output == "description=Authorized managed homebrew-actions workflow update\n"
    assert log == "enable\n"

    result, output, log = reconcile("failure")
    assert result.returncode == 0, result.stderr
    assert output == "description=Manual review required; auto-merge disabled\n"
    assert log == "disable\n"

    result, output, log = reconcile("success", enable_fail=True)
    assert result.returncode != 0
    assert log == "enable\ndisable\n"
    assert output == ""


def main() -> None:
    assert_authorization()
    assert_reconcile()
    print("Homebrew update policy passed")


if __name__ == "__main__":
    main()
