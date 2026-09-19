# homebrew-actions

Generate, validate, and publish a Homebrew Formula from a product repository.

`homebrew-actions` owns Formula rendering, Homebrew validation, and publishing to a
destination tap. The product repository owns its build and GitHub Release. The tap
repository owns published `Formula/*.rb` state.

## Quick start

### 1. Describe the Formula

Add `.github/homebrew/formula.yml` to the product repository:

```yaml
name: example
desc: Example CLI
license: MIT

install: |
  system "go", "build", *std_go_args(ldflags: "-s -w"), "./cmd/example"

test: |
  system bin/"example", "--version"
```

The `name` in this file is the Formula identity. Workflows do not repeat it.

### 2. Check pull requests

Add a reusable-workflow job to the product's pull-request CI:

```yaml
jobs:
  homebrew:
    uses: jinyongp/homebrew-actions/.github/workflows/check.yml@<full-sha> # v2.0.0
```

The check is read-only. It renders the Formula from the caller revision and runs the
Homebrew spec validation path. The stable result job is `homebrew-check`.

### 3. Publish after the product release

After the product build and GitHub Release are complete, publish the Formula for the
same immutable source commit:

```yaml
jobs:
  homebrew:
    uses: jinyongp/homebrew-actions/.github/workflows/publish.yml@<full-sha> # v2.0.0
    with:
      commit: ${{ needs.release.outputs.commit }}
      version: ${{ needs.release.outputs.version }}
    secrets:
      tap_deploy_key: ${{ secrets.HOMEBREW_TAP_DEPLOY_KEY }}
```

`publish.yml` renders the Formula, validates it on the required native Homebrew
runners, and updates the tap only after validation succeeds. It returns:

- `formula`: Formula name from the spec;
- `version`: normalized Formula version;
- `state`: `published` when the tap changed, otherwise `unchanged`.

Always pin cross-repository workflows to a full commit SHA. The adjacent `vX.Y.Z`
comment is release metadata for review and dependency tooling.

## GitHub Release distributions

When the Formula installs prebuilt GitHub Release assets, declare them in the same spec:

```yaml
name: example
desc: Example CLI
license: MIT

distribution:
  type: github-release
  tag: "v{version}"
  assets:
    macos-arm64: example_macos_arm64.tar.gz
    macos-x86_64: example_macos_x86_64.tar.gz
    linux-arm64: example_linux_arm64.tar.gz
    linux-x86_64: example_linux_x86_64.tar.gz

install: |
  bin.install "example"

test: |
  system bin/"example", "--version"
```

The referenced release must already exist when `publish.yml` runs. Release creation,
asset upload, version selection, and product build ordering remain product
responsibilities.

## Tap write credential

Publishing requires exactly one credential with write access to the destination tap:

- `tap_deploy_key`: SSH deploy key;
- `tap_token`: token with repository contents write access.

A deploy key keeps write authority scoped to the tap repository. The included setup
script can provision one and store the private key directly as a source-repository
Actions secret without printing it:

```sh
SOURCE_REPO=owner/product scripts/setup-deploy-key.sh
```

The default secret name is `HOMEBREW_TAP_DEPLOY_KEY`. Use `--force` only for an
intentional key rotation.

## Advanced options

Both workflows default to:

- tap repository: `jinyongp/homebrew-tap`;
- tap branch: `main`;
- spec path: `.github/homebrew/formula.yml`.

Override these only for another tap or a test fixture:

```yaml
with:
  tap-repository: owner/homebrew-tap
  tap-branch: main
  spec-path: .github/homebrew/formula.yml
```

The publish workflow additionally requires `commit` and `version`. `commit` must be
the full source SHA used by the product release; the checked-out source is verified
against it before Formula rendering.

## Formula ownership

The spec contains product-specific Homebrew intent such as metadata, dependencies,
install/test behavior, optional stanzas, and release-asset names.

The automation owns generated Formula structure, class naming, source URLs, checksums,
platform blocks, field ordering, native validation, tap commit creation, and bounded
fetch/rebase/retry when the tap advances concurrently. It never force-pushes the tap.

## Validation model

`check.yml` uses spec validation and does not require a tap write credential.

`publish.yml` uses release validation. For GitHub Release distributions it verifies the
published immutable release, source commit, declared assets, and SHA-256 digests, then
installs/tests the generated Formula on every required native runner before publishing.

Every reusable workflow checks out its implementation from
`job.workflow_repository@job.workflow_sha`, so a full-SHA workflow pin also pins its
internal renderer and scripts.

## Development

Run deterministic regressions locally:

```sh
python3 test/formula-generator.py
python3 test/workflow-contracts.py
python3 test/publish-scripts.py
python3 test/setup-deploy-key.py
```

CI runs the regression suite on Linux and macOS and lints the reusable workflows.

## License

MIT
