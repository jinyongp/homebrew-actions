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


def assert_publish_contract() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()

    assert "permissions:\n  contents: read" in text
    public = text.split("permissions:", 1)[0]
    for required in [
        "      formula:",
        "      ref:",
        "      version:",
        "      tap-repository:",
        "      tap-branch:",
        "      spec-path:",
    ]:
        assert required in public, required

    assert "      tap_token:" in public
    assert "      tap_deploy_key:" in public
    assert "      repository:" not in public
    assert "      dry-run:" not in public
    assert "      validation-mode:" not in public

    assert "run: bash automation/internal/scripts/validate-publish-inputs.sh" in text
    assert "run: bash automation/internal/scripts/select-tap-credential.sh" in text

    assert "repository: ${{ job.workflow_repository }}" in text
    assert "ref: ${{ job.workflow_sha }}" in text
    assert "repository: ${{ github.repository }}" in text
    assert "ref: ${{ inputs.ref }}" in text

    assert "validation-mode: release" in text
    assert "\n  homebrew-check:" in text
    assert "\n  publish:" in text
    assert "      - homebrew-check" in text

    assert "repository: ${{ inputs.tap-repository }}" in text
    assert "ref: ${{ inputs.tap-branch }}" in text
    assert "token: ${{ secrets.tap_token }}" in text
    assert "ssh-key: ${{ secrets.tap_deploy_key }}" in text
    assert "TAP_BRANCH: ${{ inputs.tap-branch }}" in text


def main() -> None:
    assert_check_contract()
    assert_publish_contract()
    print("Homebrew workflow contracts passed")


if __name__ == "__main__":
    main()
