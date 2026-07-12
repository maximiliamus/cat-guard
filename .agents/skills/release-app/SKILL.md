---
name: release-app
description: "Run a full CatGuard application release: verify tests, bump the app version and changelog, commit the release, create or move the version tag when explicitly requested, push branch and tag, wait for GitHub CI/CD to finish, automatically fix actionable CI/CD failures and retry the release, and report the final result. Use when the user asks to release the app, cut a release, bump-and-release, tag-and-push a release, or automate the release pipeline."
---

# Release App

## Overview

Execute the CatGuard release workflow end to end, from local verification through
GitHub Actions completion. Keep the release atomic: tested commit, matching
version tag, pushed branch, pushed tag, observed CI/CD result.

If CI/CD fails after the release is pushed, inspect the logs, fix actionable
repo-local failures automatically, commit the fix, move the release tag to the
new commit, push again, and watch the pipeline again. Keep retries bounded.

## Preconditions

- Work from the intended release branch, normally `master`.
- Check `git status --short` before changing files.
- Do not include unrelated dirty or untracked files in the release commit.
- Use `gh` to monitor GitHub Actions; if unauthenticated, ask the user to run
  `gh auth login` with `repo` and `workflow` scopes.
- If the requested release tag already exists, do not move it unless the user
  explicitly asked to re-tag or force-update the tag.
- During an automatic retry for the same release attempt, it is allowed to move
  the just-created release tag to the fix commit. Force-update only that tag.

## Workflow

### 1. Resolve Release Version

Read the user's requested version:

- Explicit version: `0.6.0`, `v0.6.0`, `1.0.0`.
- Relative bump: `major`, `minor`, `patch`.

If the target is missing or ambiguous, read `pyproject.toml`, state the current
version and the computed options, then ask the user to choose. Ask for explicit
confirmation before a major bump.

### 2. Run Local Tests

Run the CI-equivalent non-integration suite before committing:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not integration"
```

On non-Windows systems or when `.venv` is absent, use the active project Python:

```bash
python -m pytest -m "not integration"
```

If tests fail, stop, summarize the failure, and fix only after the user approves
or the request clearly includes fixing release blockers.

### 3. Bump Version

Use the `bump-app-version` skill when available:

1. Read its `SKILL.md`.
2. Apply its version calculation and changelog procedure.
3. Update `pyproject.toml`, `CHANGELOG.md`, and any version-bearing files.

If `bump-app-version` is unavailable, follow the same behavior manually:

- Update `[project].version` in `pyproject.toml`.
- Promote all `## [Unreleased]` changelog content into
  `## [VERSION] — YYYY-MM-DD`.
- Search for literal old-version strings in version-bearing files, excluding
  `build/`, `dist/`, `.venv/`, and `*.egg-info/`.

After edits, validate:

```bash
python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
git diff --check
```

### 4. Commit Release

Stage only release-related files. Review the staged set with:

```bash
git diff --cached --name-status
```

Commit with:

```bash
git commit -m "Bump version to VERSION"
```

If release-blocker fixes were also required, commit them separately before the
version commit unless the user explicitly wants one combined commit.

### 5. Tag The Release Commit

Create an annotated tag on the release commit:

```bash
git tag -a vVERSION -m "vVERSION"
```

If replacing an existing tag was explicitly requested:

```bash
git tag -fa vVERSION -m "vVERSION"
```

Verify the tag resolves to the release commit:

```bash
git show --no-patch --format="%h %s" "vVERSION^{}"
```

### 6. Push Branch And Tag

Push the branch first, then the tag:

```bash
git push origin BRANCH
git push origin vVERSION
```

When intentionally moving an existing tag, force-update only that tag:

```bash
git push origin vVERSION --force
```

Never use a broad force push.

### 7. Wait For CI/CD And Retry On Failure

Find the pushed runs for the release commit or tag:

```bash
gh run list --limit 10 --json databaseId,workflowName,status,conclusion,headBranch,headSha,url
```

Poll relevant runs until all terminal:

```bash
gh run view RUN_ID --json status,conclusion,url,jobs
```

Relevant runs usually include:

- `CI` on `master`.
- `Build & Release` on `vVERSION`.

Use short waits between polls. Do not leave the user without a progress update
for long-running pipelines.

If every relevant run succeeds, continue to the final report.

If any relevant run fails, fetch the failing job log:

```bash
gh run view RUN_ID --job JOB_ID --log
```

Classify the failure:

- **Actionable repo-local failure**: failed tests, lint, packaging, version/tag
  mismatch, missing committed files, source errors, or release workflow mistakes
  that can be fixed in the repository.
- **External or blocked failure**: GitHub outage, runner outage, missing secrets,
  permission/auth failure, network outage, package index outage, unavailable
  third-party service, or any change requiring user/product judgment.

For actionable repo-local failures, fix automatically:

1. Implement the smallest repo-local fix.
2. Run the relevant local verification, plus the non-integration suite when the
   failure was in tests or broadly affects runtime behavior.
3. Commit the fix with a focused message, for example:

   ```bash
   git commit -m "Fix release pipeline failure"
   ```

4. Move the release tag to the new commit:

   ```bash
   git tag -fa vVERSION -m "vVERSION"
   ```

5. Push the branch and force-update only the release tag:

   ```bash
   git push origin BRANCH
   git push origin vVERSION --force
   ```

6. Return to the start of this CI/CD wait step and monitor the new runs.

Use a maximum of three total release attempts: the initial push plus two
automatic fix-and-retry cycles. If the same failure remains after a fix, or the
retry limit is reached, stop and report the current failure with the attempted
fixes.

For external, blocked, or ambiguous failures, do not guess. Stop and report the
workflow URL, failing job, and concise log excerpt.

### 8. Final Report

Report:

- Version released.
- Release commit hash.
- Tag name and resolved commit hash.
- Push result.
- CI/CD workflows watched, number of attempts, and final conclusions.
- Any automatic fixes committed during release retry.
- Any remaining local workspace changes.

If CI/CD succeeds, say the release pipeline completed successfully. If it fails
or times out, state that the release push/tag completed but CI/CD did not pass,
and include the failure details.
