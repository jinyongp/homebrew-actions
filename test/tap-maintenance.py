#!/usr/bin/env python3
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DELETE_SCRIPT = ROOT / "internal/scripts/delete-formula.sh"
PUSH_SCRIPT = ROOT / "internal/scripts/push-tap-maintenance.sh"


def run(args, *, cwd=None, env=None, check=True):
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=check,
    )


def git(cwd, *args, check=True):
    return run(
        ["git", *args],
        cwd=cwd,
        env=dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1"),
        check=check,
    )


def configure(repo):
    git(repo, "config", "user.name", "test")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "config", "tag.gpgSign", "false")
    git(repo, "config", "core.hooksPath", "/dev/null")


def init_remote(root):
    remote = root / "remote.git"
    work = root / "work"
    concurrent = root / "concurrent"

    remote.mkdir()
    git(remote, "init", "--bare", "--initial-branch=main")
    git(root, "clone", str(remote), str(work))
    configure(work)

    formula = work / "Formula/example.rb"
    formula.parent.mkdir()
    formula.write_text('class Example < Formula\nend\n')
    git(work, "add", "Formula/example.rb")
    git(work, "commit", "-m", "test: add example formula")
    git(work, "push", "origin", "main")

    git(root, "clone", str(remote), str(concurrent))
    configure(concurrent)
    return remote, work, concurrent


def test_delete_inputs(work, temp):
    output = temp / "output"
    output.write_text("")
    env = dict(
        os.environ,
        GITHUB_OUTPUT=str(output),
        FORMULA="example",
        DRY_RUN="true",
    )
    dry_run = run(["bash", str(DELETE_SCRIPT)], cwd=work, env=env, check=False)
    assert dry_run.returncode == 0, dry_run.stderr
    assert "would delete Formula/example.rb" in dry_run.stdout
    assert (work / "Formula/example.rb").is_file()
    assert output.read_text() == "changed=true\n"

    invalid = run(
        ["bash", str(DELETE_SCRIPT)],
        cwd=work,
        env=dict(env, FORMULA="../example"),
        check=False,
    )
    assert invalid.returncode != 0
    assert "invalid formula name" in invalid.stderr

    bad_flag = run(
        ["bash", str(DELETE_SCRIPT)],
        cwd=work,
        env=dict(env, DRY_RUN="yes"),
        check=False,
    )
    assert bad_flag.returncode != 0
    assert "DRY_RUN must be true or false" in bad_flag.stderr


def test_delete_commit(work, temp):
    output = temp / "delete-output"
    output.write_text("")
    env = dict(
        os.environ,
        GITHUB_OUTPUT=str(output),
        FORMULA="example",
        DRY_RUN="false",
    )
    result = run(["bash", str(DELETE_SCRIPT)], cwd=work, env=env, check=False)
    assert result.returncode == 0, result.stderr
    assert not (work / "Formula/example.rb").exists()
    assert output.read_text() == "changed=true\n"
    assert git(work, "show", "--stat", "--oneline", "HEAD").stdout.startswith(
        git(work, "rev-parse", "--short", "HEAD").stdout.strip()
    )


def test_push_retry(remote, work, concurrent):
    marker = concurrent / "Formula/concurrent.rb"
    marker.write_text('class Concurrent < Formula\nend\n')
    git(concurrent, "add", "Formula/concurrent.rb")
    git(concurrent, "commit", "-m", "test: add concurrent formula")
    git(concurrent, "push", "origin", "main")

    env = dict(os.environ, TAP_BRANCH="main", PUSH_ATTEMPTS="3")
    result = run(["bash", str(PUSH_SCRIPT)], cwd=work, env=env, check=False)
    assert result.returncode == 0, result.stderr

    remote_example = git(
        remote, "cat-file", "-e", "main:Formula/example.rb", check=False
    )
    assert remote_example.returncode != 0
    assert git(remote, "cat-file", "-e", "main:Formula/concurrent.rb").returncode == 0

    history = git(remote, "log", "--format=%s", "-3", "main").stdout.splitlines()
    assert "chore: delete example formula" in history
    assert "test: add concurrent formula" in history


def test_push_attempt_validation(work):
    for value in ["0", "abc"]:
        result = run(
            ["bash", str(PUSH_SCRIPT)],
            cwd=work,
            env=dict(os.environ, PUSH_ATTEMPTS=value),
            check=False,
        )
        assert result.returncode != 0
        assert "PUSH_ATTEMPTS must be a positive integer" in result.stderr


def main():
    subprocess.run(["bash", "-n", str(DELETE_SCRIPT), str(PUSH_SCRIPT)], check=True)

    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        remote, work, concurrent = init_remote(temp)
        test_delete_inputs(work, temp)
        test_push_attempt_validation(work)
        test_delete_commit(work, temp)
        test_push_retry(remote, work, concurrent)

    with tempfile.TemporaryDirectory() as directory:
        empty = run(
            ["bash", str(ROOT / "internal/scripts/check-tap.sh")],
            env=dict(os.environ, TAP_PATH=directory),
            check=False,
        )
        assert empty.returncode == 0, empty.stderr
        assert "No Formulae" in empty.stdout

    print("tap maintenance regression passed")


if __name__ == "__main__":
    main()
