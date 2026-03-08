# Feature Specification: Self-Executable Build & Distribution

**Feature Branch**: `009-self-executable-build`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: "Behavior now: Program is python script. So, python installed is required. New behavior: Program should be self executable. Build in github pipeline. Distributed via github artefacts."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run CatGuard Without Python (Priority: P1)

A new user wants to try CatGuard on their machine. Currently they would need to install Python, create a virtual environment, and install dependencies — a significant barrier. With this feature, they download a zip archive for their platform, extract it, and run the executable inside — CatGuard starts monitoring their table immediately. No Python, no pip, no virtual environment required.

**Why this priority**: This is the core value of the feature. Without it, the feature doesn't exist. It also unblocks all other distribution scenarios.

**Independent Test**: Can be fully tested by downloading the built executable on a machine with no Python installation and verifying all existing CatGuard functionality works — camera monitoring, cat detection, sound alerts, system tray icon.

**Acceptance Scenarios**:

1. **Given** a machine with no Python installed, **When** the user runs the CatGuard executable, **Then** CatGuard starts successfully and all features function as expected.
2. **Given** a machine with no Python installed, **When** the user runs CatGuard for the first time, **Then** it downloads the YOLO model, creates default config, and starts monitoring — same as the Python version.
3. **Given** the CatGuard executable, **When** a cat appears on the table, **Then** the sound alert is triggered — confirming the packaged executable preserves full functionality.

---

### User Story 2 - Automated Build via GitHub Pipeline (Priority: P2)

A developer merges changes or creates a release. The GitHub Actions pipeline automatically builds self-contained executables for all supported platforms, without any manual steps. The developer does not need to install build tools locally or run packaging commands manually.

**Why this priority**: Automates the packaging process, ensuring consistent, reproducible builds and removing human error from the build step. Required for sustainable distribution.

**Independent Test**: Can be fully tested by triggering the GitHub Actions workflow (via a push or tag) and verifying executables are produced as workflow outputs for each target platform.

**Acceptance Scenarios**:

1. **Given** a new commit or tag is pushed to the repository, **When** the GitHub Actions pipeline runs, **Then** it produces self-contained executable files for all supported platforms without manual intervention.
2. **Given** the pipeline runs, **When** the build step completes, **Then** executables for each platform are available as pipeline outputs within the same workflow run.
3. **Given** the pipeline runs on a platform-specific build step, **When** the step fails, **Then** the pipeline reports the failure clearly with enough context to diagnose the issue.

---

### User Story 3 - Download Executable from GitHub (Priority: P3)

A user who wants to install CatGuard visits the project's GitHub page and downloads the pre-built executable for their operating system. They do not need to build from source or interact with any code.

**Why this priority**: Makes the app accessible to non-technical users. Depends on P1 and P2.

**Independent Test**: Can be tested by navigating to the GitHub project, locating a published executable artifact for the target platform, downloading it, and running it successfully.

**Acceptance Scenarios**:

1. **Given** a successful pipeline build, **When** a user visits the GitHub project, **Then** they can find and download the executable for their operating system.
2. **Given** a downloaded executable, **When** the user runs it on a supported OS with no Python installed, **Then** CatGuard operates with full functionality.

---

### Edge Cases

- What happens when the build pipeline runs on an unsupported platform or missing system dependency (e.g., no webcam access in CI)?
- How does the executable handle the first-run model download when no internet is available?
- What happens if the user's OS blocks unsigned executables (e.g., Windows SmartScreen, macOS Gatekeeper)? → Known limitation for MVP; user guidance (README) explains how to allow the app.
- How does the executable behave if run from a read-only directory where it cannot write the config or model files?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The distributed program MUST run on end-user machines without requiring Python or any Python packages to be pre-installed.
- **FR-002**: The executable MUST support all features of the current Python-based CatGuard application (camera monitoring, cat detection, sound alerts, system tray, config management, model auto-download).
- **FR-003**: A GitHub Actions pipeline MUST automatically build self-contained executables on every push to the main branch (CI verification only — no release published) and on every version tag (triggers a GitHub Release with attached executables). CI verification consists of successfully building all three platform executables per FR-006; no runtime smoke test is required. A GitHub Release is published with whichever platform artifacts succeeded; individual platform failures do not block the release but are reported per FR-006. If a tag-triggered workflow is re-run, the pipeline MUST update the existing GitHub Release rather than fail on a duplicate release error.
- **FR-004**: The pipeline MUST produce executables for Windows, macOS, and desktop Linux. Headless Linux is explicitly out of scope. On version-tag builds, the pipeline MUST validate that the tag version (e.g., `v1.2.3`) matches the `version` field in `pyproject.toml`; a mismatch MUST fail the build before any packaging begins.
- **FR-005**: Built executables MUST be published as downloadable artifacts upon a successful pipeline run. For main-branch CI builds, this is satisfied by GitHub Actions artifacts (retained for 7 days). For version-tag builds, this is satisfied by GitHub Release assets (permanent), which supersede the ephemeral artifacts.
- **FR-006**: The pipeline MUST fail clearly and report errors if the executable build process does not produce a working artifact. For CI purposes, a working artifact is defined as: PyInstaller exits with code 0 and the output executable file is present and non-zero in size.
- **FR-007**: The packaging process MUST bundle all required runtime dependencies (including the YOLO model loader, audio playback, and system tray components) into the single executable.

### Assumptions

- The existing Python codebase requires no architectural or structural changes to support packaging as a self-contained executable. Minor packaging-compatibility fixes (such as resource path resolution for bundled assets) are expected and do not constitute structural changes.
- Executables are distributed via GitHub Releases (permanent, versioned), making them accessible through the project's GitHub Releases page for end-user download.
- Build is triggered on every push to main (CI verification — build runs but no release is published) and on every version tag (triggers a GitHub Release with executables attached).
- The distributed artifact will be a single downloadable archive per platform (a zip containing the executable and its bundled runtime). This is not an installer package; the user extracts the archive and runs the executable directly.
- Code signing of executables is out of scope for MVP. OS security warnings (Windows SmartScreen, macOS Gatekeeper) are a known limitation; user-facing documentation will explain how to allow the app.

## Clarifications

### Session 2026-03-08

- Q: Should publishing to GitHub Releases happen on every push to main, on tags only, or both? → A: Tag-only publishes to GitHub Releases; pushes to main only run CI (build + verify, no release).
- Q: Should unsigned executables be a blocker or an accepted known limitation? → A: Accepted known limitation for MVP; user guidance in documentation explains how to allow the app on each OS.
- Q: Should the Linux executable support headless Linux or desktop Linux only? → A: Desktop Linux only; headless Linux is explicitly out of scope.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with no Python installation can download and successfully run CatGuard on a supported operating system within 5 minutes of finding the download link.
- **SC-002**: 100% of existing CatGuard features function correctly in the packaged executable, verified against the same scenarios as the Python version.
- **SC-003**: The GitHub Actions pipeline completes a full build and produces downloadable executables without manual intervention within 15 minutes of being triggered.
- **SC-004**: Executables are available for download from the GitHub project page within 30 minutes of a successful pipeline run.
- **SC-005**: The pipeline build is fully reproducible — the same source code produces behaviorally equivalent executables across repeated builds. Behavioral equivalence means all features listed in FR-002 work correctly in every build from the same source revision.
