#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "internal" / "scripts"


def run(script: str, *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = dict(os.environ)
    merged.update(env)
    return subprocess.run(
        ["bash", str(SCRIPTS / script)],
        cwd=cwd,
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    )


def configure(repo: Path) -> None:
    for key, value in [
        ("user.name", "test"),
        ("user.email", "test@example.invalid"),
        ("commit.gpgsign", "false"),
        ("tag.gpgSign", "false"),
        ("core.hooksPath", "/dev/null"),
    ]:
        subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def assert_preflight() -> None:
    with tempfile.TemporaryDirectory() as directory:
        cwd = Path(directory)
        base = {
            "COMMIT": "a" * 40,
            "VERSION": "v1.2.3",
            "TAP_REPOSITORY": "owner/homebrew-tap",
            "TAP_BRANCH": "main",
        }

        ok = run("validate-publish-inputs.sh", cwd=cwd, env=base)
        assert ok.returncode == 0, ok.stderr

        bad_commit = run(
            "validate-publish-inputs.sh",
            cwd=cwd,
            env={**base, "COMMIT": "main"},
        )
        assert bad_commit.returncode != 0
        assert "full 40-character SHA" in bad_commit.stderr

        bad_repo = run(
            "validate-publish-inputs.sh",
            cwd=cwd,
            env={**base, "TAP_REPOSITORY": "../tap"},
        )
        assert bad_repo.returncode != 0
        assert "owner/name" in bad_repo.stderr

        bad_branch = run(
            "validate-publish-inputs.sh",
            cwd=cwd,
            env={**base, "TAP_BRANCH": "main\nother"},
        )
        assert bad_branch.returncode != 0
        assert "single-line" in bad_branch.stderr


def assert_credentials() -> None:
    with tempfile.TemporaryDirectory() as directory:
        cwd = Path(directory)

        def choose(token: str = "", deploy_key: str = ""):
            output = cwd / "output"
            output.write_text("")
            result = run(
                "select-tap-credential.sh",
                cwd=cwd,
                env={
                    "GITHUB_OUTPUT": str(output),
                    "TAP_TOKEN": token,
                    "TAP_DEPLOY_KEY": deploy_key,
                },
            )
            return result, output.read_text()

        result, output = choose(token="token-value")
        assert result.returncode == 0
        assert output == "mode=token\n"

        result, output = choose(deploy_key="key-value")
        assert result.returncode == 0
        assert output == "mode=deploy_key\n"

        result, _ = choose(token="token-value", deploy_key="key-value")
        assert result.returncode != 0
        assert "not both" in result.stdout

        result, _ = choose()
        assert result.returncode != 0
        assert "Provide tap_token or tap_deploy_key" in result.stdout


def assert_commit_and_retry() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        remote = root / "tap.git"
        seed = root / "seed"
        publisher = root / "publisher"
        competitor = root / "competitor"
        verify = root / "verify"

        subprocess.run(
            ["git", "init", "--bare", "--initial-branch=main", str(remote)],
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "clone", str(remote), str(seed)], check=True, capture_output=True)
        configure(seed)
        (seed / "Formula").mkdir()
        (seed / "Formula/example.rb").write_text("old\n")
        git(seed, "add", ".")
        git(seed, "commit", "-m", "seed")
        git(seed, "push", "origin", "main")

        subprocess.run(["git", "clone", str(remote), str(publisher)], check=True, capture_output=True)
        subprocess.run(["git", "clone", str(remote), str(competitor)], check=True, capture_output=True)
        configure(publisher)
        configure(competitor)

        output = root / "commit-output"
        output.write_text("")
        no_change = run(
            "commit-formula.sh",
            cwd=publisher,
            env={
                "GITHUB_OUTPUT": str(output),
                "FORMULA_PATH": "Formula/example.rb",
                "FORMULA": "example",
                "VERSION": "1.0.0",
            },
        )
        assert no_change.returncode == 0, no_change.stderr
        assert output.read_text() == "changed=false\n"

        (publisher / "Formula/example.rb").write_text("new\n")
        output.write_text("")
        changed = run(
            "commit-formula.sh",
            cwd=publisher,
            env={
                "GITHUB_OUTPUT": str(output),
                "FORMULA_PATH": "Formula/example.rb",
                "FORMULA": "example",
                "VERSION": "1.0.0",
            },
        )
        assert changed.returncode == 0, changed.stderr
        assert output.read_text() == "changed=true\n"
        assert git(publisher, "log", "-1", "--format=%s") == "chore: update example to 1.0.0"

        (competitor / "Formula/other.rb").write_text("other\n")
        git(competitor, "add", ".")
        git(competitor, "commit", "-m", "chore: update other")
        git(competitor, "push", "origin", "main")

        pushed = run(
            "push-formula.sh",
            cwd=publisher,
            env={"TAP_BRANCH": "main", "PUSH_ATTEMPTS": "3"},
        )
        assert pushed.returncode == 0, pushed.stderr

        subprocess.run(["git", "clone", str(remote), str(verify)], check=True, capture_output=True)
        assert (verify / "Formula/example.rb").read_text() == "new\n"
        assert (verify / "Formula/other.rb").read_text() == "other\n"

        subjects = git(verify, "log", "--format=%s", "-3").splitlines()
        assert "chore: update example to 1.0.0" in subjects
        assert "chore: update other" in subjects

        push_script = (SCRIPTS / "push-formula.sh").read_text()
        assert "force" not in push_script.lower()


def main() -> None:
    assert_preflight()
    assert_credentials()
    assert_commit_and_retry()
    print("Homebrew publish scripts passed")


if __name__ == "__main__":
    main()
