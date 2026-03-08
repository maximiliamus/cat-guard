# Build & Distribution Requirements Checklist: Self-Executable Build

**Purpose**: Author self-check before opening a PR. Validates requirement quality across all three domains: packaging, CI/CD pipeline, and distribution. Tests whether requirements are complete, clear, consistent, and measurable — not whether the implementation works.
**Created**: 2026-03-08
**Reviewed**: 2026-03-08
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md) | [data-model.md](../data-model.md) | [contracts/build-artifacts.md](../contracts/build-artifacts.md)

---

## Requirement Completeness

- [x] CHK001 - Are requirements defined for what happens when the PyInstaller build produces an artifact that is structurally valid but functionally broken (e.g., missing hidden import detected only at launch)? [Completeness, Gap]
  > **PASS** — Resolved. FR-006 updated to define "working artifact" as: PyInstaller exits with code 0 and the output executable file is present and non-zero in size.

- [x] CHK002 - Are requirements specified for how the `main.py` asset path patch behaves when `sys._MEIPASS` is not set (i.e., in development mode)? [Completeness, Spec §data-model.md]
  > **PASS** — data-model.md specifies the else-branch: `Path(__file__).parent.parent.parent`. Development mode is covered.

- [x] CHK003 - Does the spec define requirements for which Python version the CI runners must use, and is that version pinned or floating? [Completeness, Spec §FR-003]
  > **PASS** — plan.md specifies Python 3.11. Constitution constrains Python 3.11+. Sufficient.

- [x] CHK004 - Are requirements defined for what "CI verification" means in FR-003 — is a successful build sufficient, or must the executable also be launched headlessly to verify it starts? [Completeness, Spec §FR-003]
  > **PASS** — Resolved. FR-003 updated to define CI verification as: successfully building all three platform executables per FR-006. No runtime smoke test required.

- [x] CHK005 - Are requirements specified for the `pyinstaller-hooks-contrib` version, or is it left unpinned? [Completeness, Gap]
  > **PASS** — Implementation detail; SC-005 (reproducibility) implicitly covers build tool stability without requiring spec-level version pinning.

- [x] CHK006 - Does the spec define requirements for the README update that explains OS security warnings (SmartScreen, Gatekeeper)? [Completeness, Spec §Assumptions]
  > **PASS** — Edge cases section specifies "user guidance (README) explains how to allow the app." Location (README) and intent (per-OS allow guidance) are specified. Sufficient for MVP.

- [x] CHK007 - Are requirements specified for what "all features function correctly" means in FR-002 and SC-002 — is a feature list or test suite referenced? [Completeness, Spec §FR-002, §SC-002]
  > **PASS** — FR-002 enumerates features explicitly. SC-002 references "same scenarios as the Python version" (the existing integration test suite). Sufficient.

---

## Requirement Clarity

- [x] CHK008 - Is "self-contained executable" defined in the spec — does it mean `--onefile` or `--onedir` + zip, and is this explicitly stated? [Clarity, Spec §FR-001, Assumption §4]
  > **PASS** — Resolved. Assumption §4 updated to "single downloadable archive per platform (zip containing the executable and its bundled runtime)."

- [x] CHK009 - Is "single executable file per platform" in Assumptions §4 consistent with the `--onedir` + zip decision in research.md, or does it create an ambiguity between "file" and "archive"? [Clarity, Ambiguity, Spec §Assumptions]
  > **PASS** — Resolved. Same fix as CHK008.

- [x] CHK010 - Is "desktop Linux" defined with sufficient precision — does it mean X11 only, Wayland only, or both? [Clarity, Spec §FR-004, §Clarifications]
  > **PASS** — "Desktop Linux" is a commonly understood term inclusive of both X11 and Wayland. "Headless Linux explicitly out of scope" is the operative clarification. The existing codebase handles both display servers.

- [x] CHK011 - Is "within 15 minutes" in SC-003 defined per-platform or for the entire pipeline run (all 3 platforms)? [Clarity, Spec §SC-003]
  > **PASS** — "The pipeline...within 15 minutes of being triggered" clearly refers to total wall clock time. Parallel matrix jobs run all three platforms within this single window.

- [x] CHK012 - Is "downloadable artifacts associated with the GitHub repository" in FR-005 specific enough to distinguish between Actions artifacts (7-day retention) and GitHub Release assets (permanent)? [Clarity, Spec §FR-005]
  > **PASS** — Resolved. FR-005 updated to explicitly distinguish: CI builds → Actions artifacts (7-day); tag builds → GitHub Release assets (permanent).

- [x] CHK013 - Does FR-006 define what "clearly" means for pipeline failure reporting — e.g., must the failure message include the failing platform, the failing step, and a log excerpt? [Clarity, Spec §FR-006]
  > **PASS** — US-2 Acceptance Scenario 3 operationalizes it: "with enough context to diagnose the issue." GitHub Actions log output satisfies this by default. Sufficient for MVP.

- [x] CHK014 - Is the term "functionally identical" in SC-005 (reproducible builds) defined with measurable criteria — are byte-for-byte identical binaries required, or behavioral equivalence sufficient? [Clarity, Spec §SC-005]
  > **PASS** — Resolved. SC-005 updated to "behaviorally equivalent executables," defined as all FR-002 features working correctly in every build from the same source revision.

---

## Requirement Consistency

- [x] CHK015 - Does the trigger described in FR-003 ("every push to the main branch") align with the clarification ("pushes to main only run CI") — is the CI-only distinction explicit in FR-003 itself? [Consistency, Spec §FR-003, §Clarifications]
  > **PASS** — FR-003 explicitly states "CI verification only — no release published" in parentheses. Consistent with clarifications.

- [x] CHK016 - Does Assumption §4 ("single file per platform") conflict with the plan's `--onedir` + zip approach? Is the assumption updated or superseded? [Consistency, Conflict, Spec §Assumptions, plan.md]
  > **PASS** — Resolved. Same fix as CHK008.

- [x] CHK017 - Are the three target platforms listed in FR-004 consistent with the matrix runners specified in the plan (`windows-latest`, `macos-latest`, `ubuntu-latest`)? [Consistency, Spec §FR-004, plan.md]
  > **PASS** — FR-004 (Windows, macOS, desktop Linux) maps directly to plan runners. Consistent.

- [x] CHK018 - Does SC-001 ("within 5 minutes of finding the download link") align with SC-004 ("within 30 minutes of a successful pipeline run") — are these measuring different things without conflict? [Consistency, Spec §SC-001, §SC-004]
  > **PASS** — SC-001 measures user experience (download + run); SC-004 measures pipeline latency (artifact availability). Complementary, not conflicting.

- [x] CHK019 - Are the "supported platforms" referenced in User Story 1 and SC-001 consistent with the platforms listed in FR-004? [Consistency, Spec §US-1, §FR-004]
  > **PASS** — US-1, SC-001, and FR-004 all reference the same three-platform target. Consistent.

---

## Acceptance Criteria Quality

- [x] CHK020 - Can SC-002 ("100% of existing CatGuard features function correctly") be objectively verified without a defined feature baseline or automated test mapping? [Measurability, Spec §SC-002]
  > **PASS** — FR-002 enumerates features; SC-002 references the existing integration test suite. Running tests against the packaged executable is the verification method. Sufficient.

- [x] CHK021 - Is SC-001 ("within 5 minutes") measurable from a well-defined start point — is "finding the download link" a precise, observable moment? [Measurability, Spec §SC-001]
  > **PASS** — SC-001 is a UX aspiration metric, not a technical gate. Acceptable for MVP.

- [x] CHK022 - Can SC-005 ("functionally identical executables across repeated builds") be verified, and is "functionally identical" operationalized with a specific test or comparison method? [Measurability, Spec §SC-005]
  > **PASS** — Resolved. Same fix as CHK014.

- [x] CHK023 - Does SC-003 define the start and end points of the "15-minute" build window precisely (e.g., from workflow trigger to artifact upload complete)? [Clarity, Measurability, Spec §SC-003]
  > **PASS** — "Within 15 minutes of being triggered" (start = workflow event) and "produces downloadable executables" (end = artifact upload). Sufficiently precise.

---

## Scenario Coverage

- [x] CHK024 - Are requirements defined for the alternate flow where one platform build fails but the others succeed — must all three succeed for a release to publish, or is partial release allowed? [Coverage, Spec §FR-003, contracts/build-artifacts.md]
  > **PASS** — Resolved. FR-003 updated: partial releases are allowed — the release publishes whichever platform artifacts succeeded; individual failures are reported per FR-006.

- [x] CHK025 - Are requirements defined for the scenario where the version tag does not match the `pyproject.toml` version — is version consistency enforced or left to the developer? [Coverage, Gap]
  > **PASS** — Resolved. FR-004 updated: pipeline MUST validate tag version matches `pyproject.toml` version on tag builds; mismatch fails the build before packaging begins.

- [x] CHK026 - Are requirements specified for re-triggering a failed build without creating a duplicate GitHub Release? [Coverage, Exception Flow, Gap]
  > **PASS** — Resolved. FR-003 updated: pipeline MUST update the existing GitHub Release on re-run (not fail on duplicate).

- [x] CHK027 - Does the spec define requirements for the scenario where the YOLO model download fails on first run (no internet) in the packaged executable? [Coverage, Spec §Edge Cases]
  > **PASS** — Edge case is acknowledged. No explicit requirement = current behavior (ultralytics error) is accepted for MVP. Consistent with the spec's scope.

- [x] CHK028 - Are requirements defined for the scenario where the executable is run from a read-only directory (config/model files cannot be written)? [Coverage, Spec §Edge Cases]
  > **PASS** — Edge case is acknowledged. No explicit requirement = current OS-level error behavior is accepted for MVP.

---

## Edge Case Coverage

- [x] CHK029 - Is there a requirement specifying what happens when the CI runner lacks access to a webcam — does the build step fail, warn, or silently succeed? [Edge Case, Spec §Edge Cases]
  > **PASS** — N/A for the build step. PyInstaller does not require camera access during packaging. The edge case is a runtime concern, not a build concern.

- [x] CHK030 - Are requirements defined for Windows SmartScreen and macOS Gatekeeper blocking — specifically, what user-facing documentation is required and where must it appear? [Edge Case, Spec §Assumptions, §Clarifications]
  > **PASS** — Edge cases section specifies "user guidance (README) explains how to allow the app." Location and scope are defined. Sufficient for MVP.

- [x] CHK031 - Is there a requirement for how the executable behaves if pystray's platform backend is not available at runtime on a given Linux desktop environment (e.g., KDE vs. GNOME)? [Edge Case, Gap]
  > **PASS** — Implementation detail handled by pystray's backend detection. Out of scope for the spec.

- [x] CHK032 - Does the spec define what happens when a new version tag is pushed but the previous build artifacts are still within their 7-day retention window? [Edge Case, Gap]
  > **PASS** — N/A. Each pipeline run uploads independent artifacts. No conflict arises between runs.

---

## Non-Functional Requirements

- [x] CHK033 - Is the expected bundle size documented as a non-functional requirement or known constraint? (torch + ultralytics produce 300–600 MB bundles; no size requirement is stated.) [Non-Functional, Gap]
  > **PASS** — No size requirement needed for MVP. Large bundle size is an expected consequence of bundling torch/ultralytics, not a defect.

- [x] CHK034 - Are startup time requirements specified for the packaged executable beyond the implicit 5-minute user onboarding window in SC-001? [Non-Functional, Clarity, Spec §SC-001]
  > **PASS** — SC-001 implicitly covers startup time. No explicit startup time NFR needed for MVP.

- [x] CHK035 - Are security requirements defined for the GitHub Actions workflow permissions — is the `contents: write` scope justified and documented? [Non-Functional, Spec §FR-003, contracts/build-artifacts.md]
  > **PASS** — Implementation detail; `contents: write` is the standard minimum permission for creating GitHub Releases. Documented in contracts/build-artifacts.md.

- [x] CHK036 - Is there a requirement for CI artifact retention period and its rationale (currently 7 days in plan; not stated in spec)? [Non-Functional, Gap]
  > **PASS** — Implementation detail. Plan documents the 7-day decision. Spec-level requirement not needed.

---

## Dependencies & Assumptions

- [x] CHK037 - Is Assumption §1 ("existing Python codebase requires no structural changes") validated against the `main.py` patch required by the plan — does this asset path change constitute a structural change? [Assumption, Conflict, Spec §Assumptions, data-model.md]
  > **PASS** — Resolved. Assumption §1 updated: no architectural/structural changes required; minor packaging-compatibility fixes (e.g., resource path resolution) are expected and explicitly excluded from this constraint.

- [x] CHK038 - Are the GitHub Actions runner images (`windows-latest`, `macos-latest`, `ubuntu-latest`) documented as dependencies with known risk of breaking changes when GitHub updates them? [Dependency, Gap]
  > **PASS** — Implementation detail; runner image updates are a standard operational risk, not a spec-level concern.

- [x] CHK039 - Is the dependency on `pyinstaller-hooks-contrib` for ultralytics/torch/pystray hook correctness documented as an assumption in the spec or plan? [Dependency, Gap]
  > **PASS** — Documented in research.md. Spec-level documentation not required.

- [x] CHK040 - Is the assumption that `ultralytics` handles model download correctly inside a packaged executable (without code changes) validated and documented? [Assumption, Spec §FR-002]
  > **PASS** — FR-002 requires model auto-download to work. research.md explicitly validates this (ultralytics downloads to `~/.ultralytics/assets/`, accessible from any executable).

---

## Ambiguities & Conflicts

- [x] CHK041 - Assumption §4 states "single file per platform" but the plan uses `--onedir` + zip. Is this ambiguity resolved explicitly in the spec, or does it remain an unacknowledged conflict? [Ambiguity, Conflict, Spec §Assumptions]
  > **PASS** — Resolved. Same fix as CHK008.

- [x] CHK042 - FR-005 says artifacts must be "published as downloadable artifacts associated with the GitHub repository" — does "associated with" cover both Actions artifacts and GitHub Release assets, or only one? [Ambiguity, Spec §FR-005]
  > **PASS** — Resolved. Same fix as CHK012.

- [x] CHK043 - The spec says "build in GitHub pipeline" and "distributed via GitHub artifacts" — are "pipeline artifacts" (ephemeral) and "GitHub Release assets" (permanent) clearly distinguished in requirements? [Ambiguity, Spec §Input, §FR-005]
  > **PASS** — FR-003 and clarifications explicitly distinguish the two. The input description is vague, but FR-003 resolves it.
