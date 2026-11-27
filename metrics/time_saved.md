---
name: time_saved
label: Time saved
version: 1
scale: 0-100
---
# Time saved

Ranks ideas by the working time they free up each month. It ignores effort and other benefits.

You do **not** produce the score. Fill the two inputs below; the app computes the number from the
formula in this file.

## Inputs

| Input | Unit | Useful knowledge base files |
|---|---|---|
| cases | cases per month: how often the process the idea changes runs. **Not** the number of people. | `departments/*.md` (volumes), `it/data-inventory.csv` (volumes) |
| minutes_saved | minutes of work saved per case, across everyone involved | `departments/*.md` (current values) |

A number you converted or derived, such as "5 a week" to 20 a month, or "2 hours a week" to
minutes per case, is an `estimate`, not a quote. Count working time only, not waiting time. If
nothing states or implies the time a case takes, leave `minutes_saved` unknown.

## Computation

Read by `portal/scoring.py`.

```yaml
formula: 100 * log10(1 + cases * minutes_saved / 60) / log10(1 + 1000)
inputs:
  cases:
    unit: cases per month
    required: true
    quote_must_contain_value: true
  minutes_saved:
    unit: minutes per case
    required: true
```

The result is rounded and limited to 0-100. The logarithm keeps large processes from dominating:
a score of 100 needs 1,000 hours a month.
