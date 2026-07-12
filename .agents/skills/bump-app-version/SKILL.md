---
name: bump-app-version
description: "Bump the application version, update CHANGELOG.md, and update any other version-bearing files. Understands explicit versions (e.g. '0.6.0') and relative bump types: 'update major version', 'update minor version', 'update patch version'."
---

# Bump Application Version

Read the argument, compute the new version, update all version-bearing files, and finalize the changelog.

## Input

The user specifies a version bump in one of two forms:

| Form | Examples |
|---|---|
| Explicit version | `0.6.0`, `v0.6.0`, `1.0.0` |
| Relative bump | `major`, `minor`, `patch` — or longer phrases like "update minor version", "bump patch" |

## Procedure

### 1. Read Current Version

Read `pyproject.toml` and extract the current `version` field under `[project]`:

```toml
[project]
version = "X.Y.Z"
```

Parse it into three integers: `MAJOR`, `MINOR`, `PATCH`.

### 2. Compute New Version

- **Explicit version supplied** (e.g. `"0.6.0"` or `"v0.6.0"`): strip the leading `v` if present; use as-is.
- **`major` / "update major version"**: new version = `(MAJOR+1).0.0`
- **`minor` / "update minor version"**: new version = `MAJOR.(MINOR+1).0`
- **`patch` / "update patch version"**: new version = `MAJOR.MINOR.(PATCH+1)`

State the computed new version clearly before making any changes and ask for confirmation if it is a major bump or if the user's instruction was ambiguous.

### 3. Update `pyproject.toml`

Replace the `version` line under `[project]`:

```toml
version = "NEW_VERSION"
```

### 4. Update `CHANGELOG.md`

The file follows Keep-a-Changelog / semver conventions:

```markdown
## [Unreleased] — …
…content…

---

## [X.Y.Z] — YYYY-MM-DD
```

**Steps:**

1. Read `CHANGELOG.md`.
2. Locate every section that starts with `## [Unreleased]`.
3. Merge all `[Unreleased]` sections into one combined content block: if there are multiple, combine their bullet lists under the appropriate `### Added / Changed / Fixed / Removed / Performance` headers, deduplicating sub-headings.
4. Remove all the original `[Unreleased]` sections from the file.
5. Insert a new versioned section immediately above the first existing versioned release (i.e. at the top of the release history, after the file's preamble):

```markdown
## [NEW_VERSION] — YYYY-MM-DD

<merged content from Unreleased sections>

---
```

If there were no `[Unreleased]` sections, insert an empty versioned section in the same position with a `### Added` placeholder.

### 5. Check Other Version-Bearing Files

Search the repository for other files that may contain a hardcoded version string matching the *old* version (`OLD_VERSION`):

- `README.md` — scan for the old version string. If found, update it.
- Any `*.cfg`, `*.ini`, `setup.py`, `*.spec` files — scan for `version = "OLD_VERSION"` or `version: OLD_VERSION`.
- Do **not** modify files in `build/`, `dist/`, `.venv/`, or `*.egg-info/`.

For each file where the old version string is found, update it to the new version and report which files were changed.

### 6. Report Changes

After all edits, output a brief summary:

```
Version bumped: OLD_VERSION → NEW_VERSION (YYYY-MM-DD)

Files updated:
  pyproject.toml          version = "NEW_VERSION"
  CHANGELOG.md            [Unreleased] → [NEW_VERSION]
  <any other files>
```

### 7. Offer Next Steps (Optional)

Ask the user if they would like to:

- **Commit** the changes: `git add pyproject.toml CHANGELOG.md && git commit -m "Bump version to NEW_VERSION"`
- **Tag** the commit: `git tag vNEW_VERSION`
- **Push**: `git push && git push --tags`

Do **not** run any of these automatically — wait for explicit confirmation before executing git operations.

## Notes

- Never downgrade the version (new version must be strictly greater than current).
- If the CHANGELOG has no `[Unreleased]` section, create one and add the release entry below it.
- Keep the existing changelog entries unchanged — only the header and structure change, not the bullet content.
- The `catguard.spec` PyInstaller spec file may not contain a version string; only update it if the old version string is literally present in the file.
