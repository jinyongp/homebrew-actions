# homebrew-actions

Reusable GitHub Actions workflows for generating, validating, and publishing Homebrew
Formulae.

This repository owns Homebrew automation. Product builds and GitHub Releases remain in
the product repository, while published Formula state remains in the destination tap.

## Public workflows

Consumers use full commit SHAs:

```yaml
uses: jinyongp/homebrew-actions/.github/workflows/check.yml@<full-sha> # v1.0.0
```

```yaml
uses: jinyongp/homebrew-actions/.github/workflows/publish.yml@<full-sha> # v1.0.0
```

```yaml
uses: jinyongp/homebrew-actions/.github/workflows/update-policy.yml@<full-sha> # v1.0.0
```

The adjacent `vX.Y.Z` comment is release metadata for humans and dependency tooling.
The full SHA is the executable dependency identity.

## Formula specification

A product owns `.github/homebrew/formula.yml`.

A source distribution is the default:

```yaml
desc: Example CLI
homepage: https://github.com/example/example
license: MIT

install: |
  system "go", "build", *std_go_args(ldflags: "-s -w"), "./cmd/example"

test: |
  system bin/"example", "--version"
```

A product backed by GitHub Release assets declares them explicitly:

```yaml
distribution:
  type: github-release
  tag: "v{version}"
  assets:
    macos-arm64: example_macos_arm64.tar.gz
    macos-x86_64: example_macos_x86_64.tar.gz
    linux-arm64: example_linux_arm64.tar.gz
    linux-x86_64: example_linux_x86_64.tar.gz
```

GitHub Release creation is not part of this repository. For a
`github-release` Formula, the required release and assets must already exist before the
publish workflow runs.

## Pull request check

The check workflow is read-only. It uses the caller repository and caller event revision
as the source and does not accept tap write credentials.

```yaml
name: Homebrew

on:
  pull_request:
    branches:
      - main

permissions:
  contents: read

jobs:
  homebrew:
    uses: jinyongp/homebrew-actions/.github/workflows/check.yml@<full-sha> # v1.0.0
    with:
      formula: example
```

The stable job is named `homebrew-check`.

## Publish

Publishing requires an immutable source commit SHA and an explicit product version.

```yaml
jobs:
  homebrew:
    permissions:
      contents: read
    uses: jinyongp/homebrew-actions/.github/workflows/publish.yml@<full-sha> # v1.0.0
    with:
      formula: example
      ref: ${{ needs.release.outputs.commit }}
      version: ${{ needs.release.outputs.version }}
    secrets:
      tap_deploy_key: ${{ secrets.HOMEBREW_TAP_DEPLOY_KEY }}
```

`publish.yml` performs Formula generation and native validation before it checks out
the destination tap with write authority. It accepts exactly one write credential:

- `tap_deploy_key`: an SSH deploy key with write access to the tap; or
- `tap_token`: a token with contents write access to the tap.

The destination defaults to `jinyongp/homebrew-tap@main`. Override
`tap-repository` and `tap-branch` for a different tap.

If the rendered Formula is unchanged, no commit or push occurs. Concurrent tap updates
use bounded fetch/rebase/retry and never force-push.

## Deploy key setup

From a clone of this repository:

```sh
SOURCE_REPO=owner/product scripts/setup-deploy-key.sh
```

The script creates a write deploy key in `jinyongp/homebrew-tap` and sends the private
key directly to the source repository Actions secret
`HOMEBREW_TAP_DEPLOY_KEY`. It does not print the private key.

Use `--force` only when intentionally rotating an existing managed key/secret.

## Dependency update policy

Consumers that already auto-merge managed Homebrew automation updates use a trusted
`workflow_run` wrapper. Do not use `pull_request_target` for this policy.

The validation workflow runs on `pull_request`. A separate workflow on the default
branch observes its completion:

```yaml
name: Homebrew automation policy

on:
  workflow_run:
    workflows:
      - CI
    types:
      - completed

permissions:
  contents: write
  pull-requests: write
  statuses: write

jobs:
  policy:
    if: >-
      github.event.workflow_run.event == 'pull_request' &&
      github.event.workflow_run.pull_requests[0].number != null
    uses: jinyongp/homebrew-actions/.github/workflows/update-policy.yml@<full-sha> # v1.0.0
    with:
      pr-number: ${{ github.event.workflow_run.pull_requests[0].number }}
      pr-head-sha: ${{ github.event.workflow_run.pull_requests[0].head.sha }}
      pr-base-sha: ${{ github.event.workflow_run.pull_requests[0].base.sha }}
      validation-event: ${{ github.event.workflow_run.event }}
      validation-conclusion: ${{ github.event.workflow_run.conclusion }}
```

The reusable policy re-fetches the pull request and verifies that its current head and
base still match the validated PR revision. It treats PR commits, changed files, and workflow text as
data only. It never checks out or executes the PR head, downloads PR artifacts, or
restores PR-produced caches.

A managed update is authorized only when:

- every PR commit is verified and authored by `dependabot[bot]`;
- only workflow files are modified;
- workflow content changes only in `homebrew-actions` full SHA references and adjacent
  stable `vX.Y.Z` comments;
- all referenced Homebrew workflows use the same SHA and release comment;
- that SHA/tag is the highest stable immutable `homebrew-actions` release;
- `check.yml`, `publish.yml`, and `update-policy.yml` all exist at the approved
  candidate SHA.

Authorization failures disable existing auto-merge and require manual review.

## Validation model

`check.yml` uses spec validation. `publish.yml` uses release validation, including
native Homebrew install/test for every runner declared by the Formula generator.

The implementation code used by every reusable workflow is checked out from
`job.workflow_repository@job.workflow_sha`. A consumer pinned to a full SHA therefore
executes scripts and internal actions from the same pinned automation revision, not from
a newer `main`.

## Development

Local deterministic regressions:

```sh
python3 test/workflow-contracts.py
python3 test/publish-scripts.py
python3 test/update-policy.py
python3 test/setup-deploy-key.py
python3 test/formula-generator.py
```

The Formula generator test requires Ruby. CI runs the suite on Linux and macOS.

## License

MIT
