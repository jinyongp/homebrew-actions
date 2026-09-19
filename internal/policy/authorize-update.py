#!/usr/bin/env python3
"""Authorize a Dependabot-only update of public homebrew-actions workflows."""

import argparse
import json
import re
from pathlib import Path

ALLOWED_DEPENDENCIES = {
    "jinyongp/homebrew-actions/.github/workflows/check.yml",
    "jinyongp/homebrew-actions/.github/workflows/publish.yml",
    "jinyongp/homebrew-actions/.github/workflows/update-policy.yml",
}
PRODUCT_PREFIX = "jinyongp/homebrew-actions/.github/workflows/"
USES_LINE = re.compile(
    r"^(?P<indent>\s*)uses:\s+"
    r"(?P<value>\"[^\"]+\"|'[^']+'|[^#\s]+)"
    r"(?:\s+#\s*(?P<comment>[^\r\n]+))?$"
)
FULL_SHA = re.compile(r"[0-9a-f]{40}")
VERSION_TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def reject(message: str) -> None:
    raise SystemExit(f"homebrew-actions update rejected: {message}")


def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        reject(f"cannot read {path}: {error}")


def validate_commits(commits, expected_count: int) -> None:
    if not isinstance(commits, list) or len(commits) != expected_count:
        reject("complete PR commit history was not retrieved")
    if not commits:
        reject("PR contains no commits")
    for commit in commits:
        author = commit.get("author") or {}
        verification = (commit.get("commit") or {}).get("verification") or {}
        if author.get("login") != "dependabot[bot]" or verification.get("verified") is not True:
            reject("every PR commit must be authored and verified by Dependabot")


def validate_changed_files(files, expected_count: int) -> None:
    if not isinstance(files, list) or len(files) != expected_count:
        reject("complete PR file list was not retrieved")
    if not files:
        reject("PR changes no files")
    for changed_file in files:
        filename = changed_file.get("filename", "")
        if (
            changed_file.get("status") != "modified"
            or not filename.startswith(".github/workflows/")
            or Path(filename).suffix not in {".yml", ".yaml"}
        ):
            reject(f"PR changes unsupported file: {filename}")
        if not isinstance(changed_file.get("patch"), str):
            reject(f"PR patch is unavailable for {filename}")


def parse_workflow_ref(line: str, source: str):
    match = USES_LINE.fullmatch(line)
    if not match:
        reject(f"cannot parse homebrew-actions workflow reference in {source}")

    value = match.group("value").strip("\"'")
    dependency, separator, ref = value.rpartition("@")
    if not separator or dependency not in ALLOWED_DEPENDENCIES:
        reject(f"unsupported homebrew-actions workflow reference in {source}")
    if FULL_SHA.fullmatch(ref) is None:
        reject(f"homebrew-actions workflow reference in {source} is not a full commit SHA")

    comment = (match.group("comment") or "").strip()
    if VERSION_TAG.fullmatch(comment) is None:
        reject(f"homebrew-actions workflow reference in {source} must have an adjacent vX.Y.Z comment")
    return dependency, ref, comment


def normalize_workflows(workflows: Path):
    refs = {dependency: [] for dependency in ALLOWED_DEPENDENCIES}
    versions = {dependency: [] for dependency in ALLOWED_DEPENDENCIES}
    normalized = {}

    for path in sorted(workflows.iterdir()):
        if path.suffix not in {".yml", ".yaml"}:
            continue
        normalized_lines = []
        for line in path.read_text().splitlines(keepends=True):
            if line.lstrip().startswith("#") or PRODUCT_PREFIX not in line:
                normalized_lines.append(line)
                continue

            content = line.rstrip("\r\n")
            line_ending = line[len(content):]
            dependency, ref, version = parse_workflow_ref(content, path.name)
            refs[dependency].append(ref)
            versions[dependency].append(version)

            normalized_line = content.replace(f"@{ref}", "@<homebrew-actions-sha>", 1)
            comment_start = normalized_line.rfind("#")
            normalized_line = (
                normalized_line[: comment_start + 1]
                + " <homebrew-actions-version>"
            )
            normalized_lines.append(normalized_line + line_ending)

        normalized[path.name] = "".join(normalized_lines)

    return normalized, refs, versions


def validate_workflows(
    base_workflows: Path,
    head_workflows: Path,
    approved_sha: str,
    approved_tag: str,
) -> None:
    base_normalized, base_refs, base_versions = normalize_workflows(base_workflows)
    head_normalized, head_refs, head_versions = normalize_workflows(head_workflows)

    if base_normalized != head_normalized:
        reject("workflow content changed beyond homebrew-actions SHA/version references")

    referenced = {
        dependency
        for dependency, dependency_refs in head_refs.items()
        if dependency_refs
    }
    if not referenced:
        reject("PR contains no homebrew-actions workflow references")

    changed = {
        dependency
        for dependency in referenced
        if (
            base_refs[dependency] != head_refs[dependency]
            or base_versions[dependency] != head_versions[dependency]
        )
    }
    if not changed:
        reject("PR contains no homebrew-actions dependency update")

    all_refs = [
        ref
        for dependency in referenced
        for ref in head_refs[dependency]
    ]
    if len(set(all_refs)) != 1:
        reject("all homebrew-actions workflows must use the same commit SHA")
    if all_refs[0] != approved_sha:
        reject("homebrew-actions workflows must use the latest immutable release SHA")

    all_versions = [
        version
        for dependency in referenced
        for version in head_versions[dependency]
    ]
    if len(set(all_versions)) != 1:
        reject("all homebrew-actions workflows must use the same release comment")
    if all_versions[0] != approved_tag:
        reject("homebrew-actions workflow comments must identify the latest immutable release")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commits", type=Path, required=True)
    parser.add_argument("--files", type=Path, required=True)
    parser.add_argument("--expected-commit-count", type=int, required=True)
    parser.add_argument("--expected-file-count", type=int, required=True)
    parser.add_argument("--approved-sha", required=True)
    parser.add_argument("--approved-tag", required=True)
    parser.add_argument("--base-workflows", type=Path, required=True)
    parser.add_argument("--head-workflows", type=Path, required=True)
    args = parser.parse_args()

    if FULL_SHA.fullmatch(args.approved_sha) is None:
        reject("approved homebrew-actions revision is not a full commit SHA")
    if VERSION_TAG.fullmatch(args.approved_tag) is None:
        reject("approved homebrew-actions release is not stable SemVer")

    validate_commits(read_json(args.commits), args.expected_commit_count)
    validate_changed_files(read_json(args.files), args.expected_file_count)
    validate_workflows(
        args.base_workflows,
        args.head_workflows,
        args.approved_sha,
        args.approved_tag,
    )


if __name__ == "__main__":
    main()
