---
name: rice
version: 2
scale: 0-100
---
# RICE business value

Ranks ideas by expected value per unit of effort: `RICE = Reach x Impact x Confidence / Effort`.

The agent does **not** produce the score. It fills the four inputs below; `scoring.py` computes the
number from this file, so the same inputs always give the same score, and changing a scale or the cap
re-ranks every idea.

## Where each input comes from

Employees often do not know the numbers. Use the knowledge base before giving up, in this order:

1. **employee**: the idea states it. `evidence` is a verbatim quote from the idea.
2. **knowledge_base**: a knowledge-base file states it. `evidence` is `knowledge-base/<file>: <verbatim text>`.
3. **estimate**: no file states it, but company facts allow a reasonable estimate. `evidence` is a one-line
   derivation; `basis` lists the facts used, each as `knowledge-base/<file>: <verbatim text>`.
   Estimates lower the idea's confidence to 0.5, so they rank below evidence-backed ideas.
4. Otherwise `null`, and add a question for the employee to `open_questions`.

| Input | Unit | Useful files |
|---|---|---|
| reach | people or cases affected per month | `departments/*.md` (volumes such as tickets per month), team sizes, `company/overview.md` (customers, sensors) |
| impact | one of the anchors below | `departments/*.md` (current values and targets) |
| confidence | one of the anchors below | what the numbers are based on |
| effort | person-months | `it/systems.csv` (API or automation available), `it/data-inventory.csv` (data quality), `projects/active-projects.md` |

## Anchors

- **Impact:** 3 = moves a department target substantially; 2 = clear measurable gain for a team;
  1 = noticeable gain; 0.5 = small; 0.25 = minimal.
- **Confidence:** 1.0 = based on data; 0.8 = based on experience; 0.5 = a guess or an estimate.
- **Effort:** person-months, at least 0.25; effort above 3 person-months is flagged.
  Confidential files (strategy, key accounts) are not available to the agent (AI usage policy).

## Config read by scoring.py

```json
{
  "impact_anchors": [3, 2, 1, 0.5, 0.25],
  "confidence_anchors": [1.0, 0.8, 0.5],
  "missing_input_confidence": 0.5,
  "estimate_confidence": 0.5,
  "min_effort": 0.25,
  "effort_flag_above": 3,
  "rice_cap": 2000
}
```

`value` (0-100) = `100 * log10(1 + RICE) / log10(1 + rice_cap)`, capped at 100. If reach or effort is still
unknown after checking the knowledge base, there is no score and the idea is shown as `needs_info`.
