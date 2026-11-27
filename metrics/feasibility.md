---
name: feasibility
label: Feasibility
version: 1
scale: 0-100
---
# Feasibility

Ranks ideas by how easy they are to build with what the company already has. It says nothing
about their value.

You do **not** produce the score. Fill the three inputs below; the app computes the number from the
formula in this file.

## Inputs

| Input | Unit | Useful knowledge base files |
|---|---|---|
| system_access | one of the anchors below | `it/systems.csv` (API or automation available) |
| data_readiness | one of the anchors below | `it/data-inventory.csv` (quality and volume), `it/data-inventory.md` |
| effort | person-months to build it | `it/systems.csv`, `projects/active-projects.md` |

## Anchors

- **System access:** 1.0 = every system involved has an API or automation, or no system is
  involved; 0.7 = most do; 0.4 = only partly, or through exports; 0.1 = no way in.
- **Data readiness:** 1.0 = the data needed exists in good quality, or none is needed;
  0.7 = it exists with some gaps; 0.4 = it exists but needs much cleaning; 0.1 = it does not exist.
- **Effort:** person-months, at least 0.25.

All three are normally estimates, based on facts from the idea or the documents.

## Computation

Read by `portal/scoring.py`.

```yaml
formula: 100 * (system_access + data_readiness) / 2 / (1 + effort / 6)
inputs:
  system_access:
    anchors: [1.0, 0.7, 0.4, 0.1]
    default: 0.4                      # used when unknown
    estimate_is_expected: true
  data_readiness:
    anchors: [1.0, 0.7, 0.4, 0.1]
    default: 0.4
    estimate_is_expected: true
  effort:
    unit: person-months
    required: true                    # without it there is no score
    min: 0.25
    flag_above: 3
    estimate_is_expected: true
```

The result is rounded and limited to 0-100. Six person-months of effort halve the score.
