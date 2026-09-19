#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def assert_check_contract() -> None:
    text = (ROOT / ".github/workflows/check.yml").read_text()

    assert "permissions:\n  contents: read" in text
    assert "secrets:" not in text
    assert "\n  publish:" not in text

    public_inputs = text.split("permissions:", 1)[0]
    for forbidden in [
        "repository:\n        required:",
        "ref:\n        required:",
        "version:\n        required:",
        "dry-run:",
        "validation-mode:",
    ]:
        assert forbidden not in public_inputs, forbidden

    assert "repository: ${{ job.workflow_repository }}" in text
    assert "ref: ${{ job.workflow_sha }}" in text
    assert "repository: ${{ github.repository }}" in text
    assert "ref: ${{ github.sha }}" in text

    assert "uses: ./automation/internal/formula" in text
    assert "validation-mode: spec" in text
    assert "name: homebrew-check-formula-${{ inputs.formula }}" in text
    assert "\n  homebrew-check:" in text

    assert "tap-repository:" in text
    assert "default: jinyongp/homebrew-tap" in text
    assert "tap-branch:" in text
    assert "default: main" in text


def main() -> None:
    assert_check_contract()
    print("Homebrew workflow contracts passed")


if __name__ == "__main__":
    main()
