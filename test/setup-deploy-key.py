#!/usr/bin/env python3
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup-deploy-key.sh"


def run(*args: str):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "TAP_REPO": ""},
    )


def main() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    unknown = run("--not-a-real-option")
    assert unknown.returncode != 0
    assert "Unknown option" in unknown.stdout

    missing_title = run("--title")
    assert missing_title.returncode != 0
    assert "--title requires a value" in missing_title.stdout

    empty_title = run("--title=")
    assert empty_title.returncode != 0
    assert "--title requires a non-empty value" in empty_title.stdout

    missing_tap = run()
    assert missing_tap.returncode != 0
    assert "TAP_REPO must specify" in missing_tap.stderr

    print("deploy-key setup argument checks passed")


if __name__ == "__main__":
    main()
