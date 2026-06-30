# Project Workflow

This file is for me, the human operator.

It explains how to run the project with AI/Codex without losing control of context.

The repository is the source of truth.
Chat history is not source of truth.
Codex output is not source of truth until it is written into the repo and committed.

---

## Core Idea

Do not use AI like this:

```text
AI generates plan
→ AI reviews plan
→ AI rewrites plan
→ AI reviews again
→ I lose confidence and keep looping
````

Use AI like this:

```text
PLAN.md
→ technical ownership review
→ phase spec
→ TODO.md
→ Codex implements one Active task
→ report
→ review
→ next Active task
→ final phase QA
```

---

## File Roles

### PROJECT.md

Project constitution.

Contains:

* project goal
* global invariants
* non-negotiable rules
* AI/Codex behavior rules

Update rarely.

Only update `PROJECT.md` when a global invariant changes.

Examples:

* allowing OOS tuning
* abandoning OHLCV-only
* changing from research pipeline to live trading
* expanding from US equities to another market

---

### PLAN.md

High-level v0 project blueprint.

Contains:

* phase overview
* phase goals
* phase inputs and outputs
* high-level QA
* high-level GO / NO-GO criteria

`PLAN.md` is not automatically a fully validated implementation plan.

Update `PLAN.md` only when the global phase blueprint changes.

Examples:

* adding a new phase
* removing a phase
* changing phase dependencies
* changing a design that affects multiple downstream phases

Do not update `PLAN.md` for small implementation details.

---

### docs/phases/phase_XX.md

Executable spec for one phase.

Contains:

* phase goal
* input contract
* output contract
* schema
* implementation constraints
* QA
* GO / NO-GO
* known risks
* provisional decisions

Create or update this before implementing a phase.

---

### TODO.md

Current execution panel.

Contains:

* one Active task
* short backlog
* acceptance criteria for the Active task
* allowed files
* disallowed files or areas

Codex implements only the Active task in `TODO.md`.

---

### reports/phase_XX/

Execution evidence.

Contains:

* task reports
* spike reports
* QA reports
* final GO / NO-GO reports

Reports describe what happened. They do not define future requirements by themselves.

---

### docs/reviews/

Technical ownership reviews.

Use these before writing phase specs.

A technical ownership review explains:

* technical choices
* pros and cons
* risks
* common failure modes
* simpler alternatives
* validation methods
* whether a choice is BLOCKER / RISK / SPIKE / NICE-TO-HAVE

---

### docs/decisions.md

Decision log.

Use this when a meaningful design decision is made.

Start with one file. Do not create many separate ADR files at the beginning.

---

### CODEX.md

Instructions for Codex.

Codex should read this before making changes.

---

## Phase Workflow

Each phase follows this sequence:

```text
1. Create phase branch
2. Run technical ownership review
3. Decide READY_TO_SPEC / NEEDS_SPIKE / NEEDS_DECISION
4. Write phase spec
5. Generate TODO.md
6. Codex implements one Active task
7. Review Codex output
8. Repeat task loop
9. Run final phase QA
10. Merge only if phase is GO
```

---

## Step 1: Create a Phase Branch

Example:

```bash
git checkout -b phase-00-trading-calendar
```

Use one branch per phase at first.

Later, if phases become too large, task branches may be used.

---

## Step 2: Ask AI for Technical Ownership Review

Use this prompt with ChatGPT or Codex in planning mode.

Do not ask it to write code.

```text
Read:

- PROJECT.md
- PLAN.md

Focus only on Phase <X>: <phase name>.

Do not rewrite the plan yet.
Do not implement code.
Do not optimize unrelated phases.

Produce a technical ownership review.

For each important technical choice in this phase, explain:

1. What problem it solves
2. Why it may be reasonable
3. Pros
4. Cons
5. Common failure modes
6. Simpler alternative
7. How to validate it with QA or a small spike
8. Classification:
   - BLOCKER
   - RISK
   - SPIKE
   - NICE-TO-HAVE

Also identify:

1. Which choices I need to understand before implementation
2. The smallest spike, if any, before writing the phase spec
3. Any contradictions with PROJECT.md

End with exactly one of:

- READY_TO_SPEC
- NEEDS_SPIKE
- NEEDS_DECISION

Write the result to:

docs/reviews/phase_<XX>_ownership_review.md
```

Commit the review if useful:

```bash
git add docs/reviews/phase_<XX>_ownership_review.md
git commit -m "Add Phase <XX> ownership review"
```

---

## Step 3: Decision / Spike Gate

After the technical ownership review, choose one path.

### If READY_TO_SPEC

Proceed to write the phase spec.

### If NEEDS_SPIKE

Create a small spike task in `TODO.md`.

Example spike task:

```text
Phase 1 Spike: Test date + ticker_bucket partition layout on 20 trading days
```

Spike output must go under:

```text
reports/phase_<XX>/spike_<name>.md
```

### If NEEDS_DECISION

Make one explicit decision.

Record it in:

```text
docs/decisions.md
```

Do not keep debating the whole phase.

---

## Step 4: Ask AI to Write the Phase Spec

Use this prompt:

```text
Read:

- PROJECT.md
- PLAN.md
- docs/reviews/phase_<XX>_ownership_review.md
- docs/decisions.md, if relevant
- relevant spike reports, if any

Write:

docs/phases/phase_<XX>_<short_name>.md

Rules:

- Focus only on Phase <X>: <phase name>.
- Convert the high-level PLAN.md section into an executable phase spec.
- Include:
  1. Goal
  2. Inputs
  3. Outputs
  4. Required schema or data contract
  5. Implementation constraints
  6. QA checks
  7. GO criteria
  8. NO-GO criteria
  9. Known risks
  10. Provisional choices
- Mark uncertain choices as provisional.
- Do not include implementation for later phases.
- Do not write code.
```

Review the phase spec yourself.

Then commit:

```bash
git add docs/phases/phase_<XX>_<short_name>.md
git commit -m "Add Phase <XX> executable spec"
```

---

## Step 5: Ask AI to Generate TODO.md for the Phase

Use this prompt:

```text
Read:

- PROJECT.md
- PLAN.md
- docs/phases/phase_<XX>_<short_name>.md

Generate TODO.md for Phase <X>: <phase name>.

Rules:

- Only include tasks for Phase <X>.
- Include exactly one Active task.
- Keep the Active task small enough for one Codex run.
- Include a short backlog.
- Every task must have clear acceptance criteria.
- The Active task must specify:
  1. Goal
  2. Allowed files
  3. Disallowed files or areas
  4. Acceptance criteria
  5. Required report path
- Do not include implementation for later phases.
```

Commit:

```bash
git add TODO.md
git commit -m "Add Phase <XX> task plan"
```

---

## Step 6: Ask Codex to Implement the Active Task

Use this prompt for Codex:

```text
Read:

- PROJECT.md
- PLAN.md
- CODEX.md
- TODO.md
- relevant docs/phases/phase_<XX>_<short_name>.md

Implement only the Active task in TODO.md.

Before coding, summarize:

1. Active task
2. Files you expect to create or modify
3. Files or areas you will not touch
4. Validation plan

Rules:

- Do not skip ahead to later phases.
- Do not modify unrelated phases.
- Do not redesign the project.
- Do not update PROJECT.md unless a global invariant truly changed.
- Do not update PLAN.md unless the global phase blueprint truly changed.
- If blocked, write a BLOCKED report instead of expanding scope.

After coding:

1. Run the smallest relevant tests or checks.
2. Write a report under the required path in TODO.md.
3. Update TODO.md only to:
   - mark the current Active task status
   - propose the next Active task
4. Stop.
```

---

## Step 7: Review Codex Output

Review manually first:

```bash
git diff
pytest
```

Then either review yourself or ask ChatGPT/Codex to review.

Use this prompt:

```text
Review this implementation against the repository source of truth.

Read:

- PROJECT.md
- PLAN.md
- TODO.md
- relevant docs/phases/phase_<XX>_<short_name>.md
- relevant report under reports/phase_<XX>/
- relevant diff or changed files

Check:

1. Did the implementation stay within the Active task scope?
2. Did it violate PROJECT.md invariants?
3. Did it accidentally implement later phases?
4. Are there leakage risks?
5. Are tests or QA checks sufficient?
6. Is the report clear and complete?
7. Should this task be classified as:
   - GO
   - PARTIAL
   - BLOCKED
   - NO-GO
8. What is the smallest next Active task for TODO.md?

Do not redesign the whole project unless there is a hard blocker.
```

If the review is GO, commit:

```bash
git add .
git commit -m "Implement Phase <XX>.<Y> <task name>"
```

If PARTIAL, create a follow-up Active task.

If BLOCKED, fix the blocker before continuing.

If NO-GO, do not continue to the next task.

---

## Step 8: Repeat the Task Loop

Repeat:

```text
TODO.md Active task
→ Codex implementation
→ report
→ review
→ commit
→ next Active task
```

Do not ask AI to repeatedly review the whole plan.

---

## Step 9: Final Phase QA

When the phase backlog is complete, create a final QA task in `TODO.md`.

Then ask Codex:

```text
Read:

- PROJECT.md
- PLAN.md
- CODEX.md
- TODO.md
- docs/phases/phase_<XX>_<short_name>.md
- all reports under reports/phase_<XX>/

Run final Phase <X> QA.

Do not implement new features unless the QA task explicitly requires a missing check.

Produce:

reports/phase_<XX>/final_qa.md

The final QA report must include:

1. Phase goal
2. Outputs produced
3. QA checks run
4. Commands run
5. Results
6. Known risks
7. Open issues
8. GO / NO-GO decision
9. Evidence for the decision
10. Readiness for next phase

If required evidence is missing, classify as NO-GO or BLOCKED.
```

---

## Step 10: Merge Only If Phase Is GO

If final QA is GO:

```bash
git checkout main
git merge phase-<XX>-<short-name>
git tag phase-<XX>-go
```

If final QA is NO-GO or BLOCKED:

* do not merge
* create a fix task in TODO.md
* continue on the phase branch

---

## Review Budget

Do not repeatedly ask AI to review the whole plan.

Each phase gets at most:

1. Technical ownership review
2. Phase spec review
3. Final QA review

If uncertainty remains after two rounds of discussion, create a spike task instead of continuing to debate.

---

## Spike Rule

Use a spike when a technical choice is unclear and discussion is not resolving it.

Examples:

* Verify calendar source against known holidays and early closes.
* Test partition layout on a small date range.
* Run a toy encoder training pass.
* Compare clustering methods on a small embedding sample.

Spike output must be written under:

```text
reports/phase_<XX>/spike_<name>.md
```

---

## Document Update Rules

Update `PROJECT.md` only when global invariants change.

Update `PLAN.md` only when the global phase blueprint changes.

Update `docs/phases/phase_XX.md` when the current phase spec changes.

Update `TODO.md` whenever the Active task changes.

Update `reports/` whenever Codex completes a task, spike, or QA step.

Update `docs/decisions.md` when a meaningful design decision is made.

Do not update `PROJECT.md` or `PLAN.md` just because an implementation detail changed.