# Proposal: extend `IdeaDraft` to the brief's eight core fields

**For whoever owns `employee_interface/`.** Nothing in this proposal has been
applied. The patch beside this file is ready to apply when you want it:

```bash
git apply compass/proposals/idea-draft-8-fields.patch
```

It has been checked against the current files with `git apply --check` and
applies cleanly.

## Why

The challenge brief fixes eight core fields for every submission:

| # | Brief's field | `IdeaDraft` today |
|---|---|---|
| 1 | Problem | `problem` |
| 2 | Intended purpose / intended use | `proposed_improvement` |
| 3 | Users and affected people | `who_is_affected` |
| 4 | Deployment context | **missing** |
| 5 | Data | **missing** |
| 6 | Expected benefit / value | `expected_benefit` |
| 7 | Effort | **missing** |
| 8 | Human oversight | **missing** |

Your four map cleanly, and they are exactly the four the brief marks as
required, so submissions through the intake chat already pass the submission
gate. The four that are missing are the ones the evaluation half cannot work
without:

- **deployment_context** decides the Article 50 transparency flag. Whether a
  customer ever sees the output is the entire test, and it cannot be inferred
  from a problem statement.
- **data** is the most common reason an idea turns out to be infeasible. The
  agent checks the named data against `knowledge-base/it/data-inventory.md`
  for quality and personal-data status.
- **effort** is the divisor in the RICE score. Without it the idea cannot be
  ranked against anything.
- **human_oversight** is required by our own AI usage policy, and is the field
  that most often turns a risky idea into an acceptable one.

## What happens today without the patch

Ideas submitted through the intake chat are assessed, and they degrade
honestly rather than silently:

- the four missing fields are recorded as `missing`, never inferred
- the EU AI Act screening returns `insufficient_information` instead of
  `minimal`, because concluding "minimal risk" on absent information is the
  one thing it must not do
- the RICE score is withheld if Effort cannot be determined, or carries a
  capped Confidence
- each gap becomes a review item assigned back to the submitter

So the system works either way. The patch is what lets an intake-chat
submission be ranked immediately instead of bouncing to the review queue.

## What the patch changes

**`idea_store.py`** — four fields added to `IdeaDraft` after
`expected_benefit`, and four sections added to `to_markdown` so they appear in
the draft the employee confirms. `missing_fields()` needs no change: it already
iterates the model, so the new fields are covered by the existing guard in
`propose_idea`.

**`app.py`** — the four new points added to the `INSTRUCTIONS` checklist, plus
one rule telling the agent to accept short answers and to record "I do not
know" as unknown rather than filling it in. That second part matters: these
four fields invite invention more than the others, and the brief forbids it.

Field names follow your existing style (`snake_case`, described in the model
docstring). `data_needed` rather than `data` avoids shadowing anything and
reads better in the chat.

## What the patch deliberately does not change

- The seven existing fields keep their names and order, so nothing downstream
  of your app breaks.
- `scope` and `current_process` stay. They are not core fields in the brief,
  but they are good context and the evaluation pipeline reads them as such.
- Storage stays markdown files under `knowledge-base/ideas/raw/`. The parser
  in `compass/records.py` reads sections by heading, so it picks the four new
  sections up automatically once they appear.
- Nothing about auth, the submit button, or the no-overwrite ID allocation.

## After applying

```bash
python -m seed.load          # re-assess, picking up the new fields
```

An intake submission should then show `8/8` in the Fields column of the board
rather than `4/8`, and reach a real risk verdict instead of
`insufficient_information`.
