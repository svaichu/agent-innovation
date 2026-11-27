---
name: rice
version: 3
scale: 0-100
---
# RICE business value

Ranks ideas by expected value per unit of effort: `RICE = Reach x Impact x Confidence / Effort`.

You do **not** produce the score. Fill the four inputs below; the app computes the number from the
formula in this file.

## Inputs

| Input | Unit | Useful knowledge base files |
|---|---|---|
| reach | cases per month: how often the process the idea changes runs (tickets, orders, invoices, tenders). **Not** the number of people. | `departments/*.md` (volumes), `it/data-inventory.csv` (volumes), `company/overview.md` |
| impact | one of the anchors below, per case and for the team | `departments/*.md` (current values and targets) |
| confidence | one of the anchors below | what the numbers are based on |
| effort | person-months | `it/systems.csv` (API or automation available), `it/data-inventory.csv` (data quality), `projects/active-projects.md` |

A number you converted or derived, such as "5 a week" to 20 a month, is an `estimate`, not a quote.

## Anchors

- **Impact:** 3 = moves a department target substantially; 2 = clear measurable gain for a team;
  1 = noticeable gain; 0.5 = small; 0.25 = minimal.
- **Confidence:** 1.0 = based on data; 0.8 = based on experience; 0.5 = a guess.
- **Effort:** person-months, at least 0.25.

Impact, confidence and effort are normally estimates. An estimated reach, or any unknown input,
limits confidence to 0.5, so ideas with evidence rank higher.

## Computation

Read by `portal/scoring.py`.

```yaml
formula: 100 * log10(1 + reach * impact * confidence / effort) / log10(1 + 10000)
inputs:
  reach:
    unit: cases per month
    required: true                    # without it there is no score
    quote_must_contain_value: true    # a quoted reach must show the number
  impact:
    anchors: [3, 2, 1, 0.5, 0.25]
    default: 0.25                     # used when unknown
    estimate_is_expected: true        # a judgement, so estimating it is normal
  confidence:
    anchors: [1.0, 0.8, 0.5]
    default: 0.5
    estimate_is_expected: true
  effort:
    unit: person-months
    required: true
    min: 0.25
    flag_above: 3
    estimate_is_expected: true        # estimating it does not lower confidence
caps:                                 # applied when an input is unknown, or reach is estimated
  confidence: 0.5
```

The result is rounded and limited to 0-100. The logarithm keeps very large reach from dominating:
a score of 100 needs a RICE value of 10,000.
