# Codex Instructions

You are working inside the `active-minute-encoder` repository.

The repository is the only source of truth. Do not rely on prior chat context if it conflicts with repo files.

---

## Required reading before changes

Before making changes, read:

1. `PROJECT.md`
2. `PLAN.md`
3. `CODEX.md`
4. `TODO.md`, if it exists
5. The relevant phase spec under `docs/phases/`, if it exists

If `TODO.md` does not exist, do not implement code unless the user explicitly asks you to create or update planning documents.

---

## Priority order

If files conflict, use this priority order:

1. `PROJECT.md`
2. Active `docs/phases/phase_XX.md`
3. `TODO.md`
4. `PLAN.md`
5. Reports under `reports/`

Rules:

- `PROJECT.md` has highest priority.
- The active phase spec overrides the matching section in `PLAN.md`.
- `TODO.md` controls what to implement now.
- Reports describe evidence and results, not future requirements.
- If there is a contradiction, stop and report it instead of guessing.

---

## Implementation rules

- Implement only the Active task in `TODO.md`.
- If `TODO.md` does not exist, do not implement code unless explicitly instructed.
- Do not skip ahead to later phases.
- Do not redesign the whole project unless the Active task is blocked by a hard contradiction.
- Do not modify unrelated phases.
- Do not introduce new dependencies unless necessary and justified.
- Prefer small, reviewable changes.
- Add or update tests or validation checks whenever practical.
- If blocked by missing data, invalid assumptions, or upstream issues, write a BLOCKED report instead of expanding scope.

---

## Planning rules

When asked to do planning, do not write code.

Planning outputs may include:

- technical ownership review
- phase spec
- TODO task plan
- decision note
- spike proposal

Planning outputs should be written into the repository.

Common output paths:

- `docs/reviews/phase_XX_ownership_review.md`
- `docs/phases/phase_XX_<short_name>.md`
- `docs/decisions.md`
- `TODO.md`
- `reports/phase_XX/spike_<name>.md`

---

## Before coding

Before coding, summarize:

1. Active task.
2. Files expected to be created or modified.
3. Files or areas that will not be touched.
4. Validation plan.

---

## After coding

After coding:

1. Run the smallest relevant tests or checks.
2. Write a report under `reports/<phase>/`.
3. Update `TODO.md` only to mark the current task and propose the next Active task.
4. Do not update `PLAN.md` unless the phase structure or global blueprint changed.
5. Do not update `PROJECT.md` unless a global invariant truly changed.

---

## Report format

Each task report should use this structure:

# <Task Name> Report

## Status

GO / PARTIAL / BLOCKED / NO-GO

## Changed files

- ...

## What was implemented

- ...

## Commands run

```bash
...
````

## Results

* ...

## QA summary

* ...

## Risks / unknowns

* ...

## Suggested next task

* ...

---

## Scope guard

If the Active task is small, keep the change small.

Do not implement future convenience features unless they are required for the Active task.

Do not use broad refactors to complete a narrow task.

Do not silently change project assumptions.

Do not modify `PLAN.md` or `PROJECT.md` without explicitly explaining why.
