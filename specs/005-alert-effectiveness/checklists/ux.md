# Requirements Quality Checklist: Alert Effectiveness — Visual Annotation & Pipeline

**Purpose**: Validate the quality, completeness, and clarity of visual annotation and pipeline requirements before planning
**Created**: 2026-03-02
**Audience**: Author (pre-plan self-review)
**Feature**: [../spec.md](../spec.md)
**Focus areas**: Visual annotation requirements · Delayed-save pipeline · Scope coherence · Acceptance criteria measurability

---

## Requirement Completeness

- [x] CHK001 — Are exact visual positioning rules defined for the outcome overlay (e.g., top-left corner, bottom bar, relative to bounding boxes)? **Resolved: outcome overlay → bottom-left corner; sound filename label → top-left corner; bounding boxes → on detected regions. Zones do not overlap. [Spec §FR-011, §FR-011a, §Assumptions updated]**
- [x] CHK002 — Is there a defined requirement for what is displayed when the default built-in alert sound plays — not a file with a human-readable filename — and FR-011a requires showing a filename? **Resolved: display "Alert: Default". [Spec §FR-011a updated]**
- [ ] CHK003 — Is the annotation layout defined for all three annotation elements rendered simultaneously (bounding box + outcome overlay + sound filename) to prevent overlap conflicts? [Completeness, Gap, Spec §FR-011]
- [ ] CHK004 — Is there a requirement specifying what happens to the pending screenshot when the application is restarted (not crashed) while a cooldown is active? [Completeness, Gap, Spec §Edge Cases]
- [ ] CHK005 — Are requirements defined for what annotation is applied when the pending screenshot is lost due to a crash during cooldown — should a partial/crash-recovery file ever be written? [Completeness, Spec §Edge Cases]

## Requirement Clarity

- [ ] CHK006 — Is "legible" (Spec §FR-002) quantified with a measurable criterion such as minimum rendered font size or minimum contrast ratio against the frame background? [Clarity, Spec §FR-002]
- [ ] CHK007 — Is "visually distinct from the background" (Spec §FR-004) defined with a specific color value or contrast threshold rather than left to implementer judgment? [Clarity, Spec §FR-004]
- [ ] CHK008 — Is "MUST NOT fully obscure the detected cat" (Spec §FR-004) defined with a measurable threshold (e.g., minimum percentage of bounding box area that must remain uncovered)? [Clarity, Spec §FR-004]
- [ ] CHK009 — Is "human-readable percentage" (Spec §FR-002) defined with a specific display format (e.g., "92%" vs "92.3%" vs "0.92") to ensure consistent rendering? [Clarity, Spec §FR-002]
- [x] CHK010 — Are the example outcome messages in FR-009 ("Cat left – alert worked!") and FR-010 ("Cat remained after alert") normative (must use exactly these words) or illustrative (any equivalent message is acceptable)? **Resolved: illustrative — FR-009/FR-010 updated with explicit note. [Spec §FR-009, §FR-010 updated]**
- [ ] CHK011 — Is "clearly visible" (Spec §SC-002, §SC-003) linked back to concrete visual requirements in FR-009/FR-010 that make it achievable and verifiable? [Clarity, Spec §SC-002]

## Requirement Consistency

- [ ] CHK012 — Are positioning and styling requirements consistent between the success overlay (FR-009) and the failure overlay (FR-010), or are they allowed to differ? [Consistency, Spec §FR-009, §FR-010]
- [x] CHK013 — Does the "unknown outcome" path (FR-012: no overlay saved when camera unavailable) align with SC-002 which states zero screenshots should be saved with a missing outcome "when a verification was possible"? **Resolved: cross-reference added to SC-002 explicitly pointing to FR-012. [Spec §SC-002 updated]**
- [ ] CHK014 — Do any in-scope requirements (FR-001–FR-012, FR-011a) implicitly depend on data or behavior from deferred requirements (FR-013–019) without an explicit decoupling statement? [Consistency, Spec §FR-011a]
- [x] CHK015 — Are the Key Entities "Re-Entry Event" and "Session Statistics" — which relate exclusively to deferred features — causing ambiguity within the in-scope requirements by their presence in the data model? **Resolved: both entities marked *(Deferred — US4)* and *(Deferred — US5)* inline in Key Entities. [Spec §Key Entities updated]**

## Acceptance Criteria Quality

- [ ] CHK016 — Is SC-001 ("within 5 seconds") linked to specific visual design constraints (font size, label position) that make it achievable by design rather than dependent on user effort? [Measurability, Spec §SC-001]
- [ ] CHK017 — Is SC-003 ("at a glance, under 3 seconds") supported by concrete visual requirements (color, size, placement) that would causally produce that response time? [Measurability, Spec §SC-003]
- [ ] CHK018 — Is SC-004 ("correct in 100% of cases") reconciled with the edge case where a cat briefly leaves and returns before the cooldown ends, resulting in a "failure" verdict — is this deliberate and documented as the intended behavior? [Measurability, Spec §SC-004, §Edge Cases]
- [x] CHK019 — Are SC-005 ("time-to-clear accuracy") and SC-006 ("effectiveness rate readable") still present in Success Criteria despite the features they measure (US3, US5) being explicitly deferred — should they be removed or marked deferred? **Resolved: marked deferred in-place. [Spec §SC-005, §SC-006 updated]**

## Scenario Coverage

- [ ] CHK020 — Is there an acceptance scenario covering what is displayed when the alert sound is the built-in default (no custom filename) and FR-011a requires showing a filename on the screenshot? [Coverage, Gap, Spec §US-2]
- [ ] CHK021 — Is there an acceptance scenario for the bounding box annotation path (US1) when the verification check cannot be performed (camera unavailable) — not just for the outcome overlay (US2)? [Coverage, Gap, Spec §US-1]
- [ ] CHK022 — Is there an acceptance scenario covering a detection event that fires simultaneously with the expiry of a previous cooldown, as described in the edge cases? [Coverage, Spec §Edge Cases]
- [ ] CHK023 — Is there a scenario specifying what annotation (if any) appears on the screenshot when multiple cats are present and only some are still in frame at verification time (partial clearance = failure)? [Coverage, Spec §Edge Cases, §FR-003]

## Edge Case Coverage

- [ ] CHK024 — Are requirements defined for how the sound filename is displayed when it contains special characters, is extremely long, or is empty/null? [Edge Case, Gap, Spec §FR-011a]
- [ ] CHK025 — Are annotation requirements specified for very low-resolution camera frames where bounding boxes and text labels may become illegible regardless of styling? [Edge Case, Gap, Spec §FR-004]
- [ ] CHK026 — Is there a defined behavior for the annotation pipeline when image encoding (JPEG compression) significantly degrades the legibility of overlaid text or bounding box lines? [Edge Case, Gap]

## Non-Functional Requirements

- [ ] CHK027 — Are NFR-001 and NFR-002 (async execution, no crash on failure) defined with acceptance criteria that can be objectively verified — e.g., measurable latency threshold or explicit failure isolation guarantee? [Measurability, Spec §NFR-001, §NFR-002]
- [ ] CHK028 — Is there a requirement defining an upper bound on memory usage for a pending screenshot held in memory during the full cooldown period? [Gap, Spec §NFR]

## Scope & Deferred Items

- [ ] CHK029 — Are the deferred FRs (FR-013 through FR-019) described with enough standalone detail that a future feature could be scoped from them without revisiting the original user request? [Completeness, Spec §FR-013]
- [ ] CHK030 — Is there an explicit requirement (not just an assumption) prohibiting implementation of deferred features (US3, US4, US5) within this release, to prevent scope creep during development? [Completeness, Gap, Spec §Assumptions]

---

## Notes

- Items marked `[Gap]` indicate missing requirements — they must be added to spec.md before planning.
- Items marked `[Ambiguity]` indicate requirements that exist but are underspecified — they need clarification.
- Items marked `[Consistency]` flag potential contradictions between sections.
- Mark items `[x]` as you address each finding. Add inline notes with the resolution.
- **Priority guidance**: CHK002, CHK010, CHK019 are the highest-risk items — resolve these before `/speckit.plan`.
