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


def assert_policy_contract() -> None:
    text = (ROOT / ".github/workflows/update-policy.yml").read_text()

    assert "pull_request_target" not in text
    assert "dependabot/fetch-metadata" not in text
    assert "actions/download-artifact" not in text
    assert "actions/cache" not in text
    assert "ref: ${{ inputs.pr-head-sha }}" not in text

    public = text.split("concurrency:", 1)[0]
    for required in [
        "      pr-number:",
        "      pr-head-sha:",
        "      pr-base-sha:",
        "      validation-event:",
        "      validation-conclusion:",
    ]:
        assert required in public, required
    assert "secrets:" not in public

    assert "repository: ${{ job.workflow_repository }}" in text
    assert "ref: ${{ job.workflow_sha }}" in text
    assert "repos/jinyongp/homebrew-actions/releases?per_page=100" in text
    assert "sort_by(.version_parts)" in text
    assert "for public_workflow in check.yml publish.yml update-policy.yml; do" in text
    assert "contents/.github/workflows/$public_workflow" in text

    assert "context=homebrew-actions/policy" in text
    assert "contents: read\n      pull-requests: read" in text
    assert "contents: write\n      pull-requests: write" in text
    assert "statuses: write" in text
    assert "automation/internal/policy/authorize-update.py" in text
    assert "automation/internal/policy/reconcile.sh" in text
    assert "EXPECTED_BASE_SHA" in text
    assert "Pull request base changed after validation." in text


def assert_repository_contract() -> None:
    release = (ROOT / ".github/workflows/release.yml").read_text()
    ci = (ROOT / ".github/workflows/test.yml").read_text()
    readme = (ROOT / "README.md").read_text()

    assert "jinyongp/release-actions" not in release
    assert "repos/$GITHUB_REPOSITORY/immutable-releases" in release
    for workflow in ["check.yml", "publish.yml", "update-policy.yml"]:
        assert f".github/workflows/{workflow}" in release

    for test in [
        "test/formula-generator.py",
        "test/workflow-contracts.py",
        "test/publish-scripts.py",
        "test/update-policy.py",
        "test/setup-deploy-key.py",
    ]:
        assert test in ci
    assert "ubuntu-24.04" in ci
    assert "macos-15" in ci
    assert "ruby/setup-ruby@" in ci
    assert "actionlint@v1.7.12" in ci

    for workflow in ["check.yml", "publish.yml", "update-policy.yml"]:
        assert f"homebrew-actions/.github/workflows/{workflow}@<full-sha>" in readme
    assert "workflow_run.pull_requests[0].head.sha" in readme
    assert "workflow_run.pull_requests[0].base.sha" in readme
    assert "Do not use `pull_request_target`" in readme


def main() -> None:
    assert_check_contract()
    assert_publish_contract()
    assert_policy_contract()
    assert_repository_contract()
    print("Homebrew workflow contracts passed")


if __name__ == "__main__":
    main()
