# Metrics

Skill files used by the Score agent. Code is in [portal/](../portal/); the contract is in
[ARCHITECTURE.md](../ARCHITECTURE.md#4-metric-contract).

| File | What it is |
|---|---|
| `rice.md` | RICE business value, with its inputs, anchors and formula. |
| `feasibility.md` | How easy an idea is to build with the systems and data at hand. |
| `time_saved.md` | Working time an idea frees each month. |
| `checks.md` | Flags shown next to any metric: AI / conventional automation / more research, and a preliminary EU AI Act screen. |

## Add or change a metric

1. Copy `rice.md`. Set `name`, `version` and, for the column heading, `label`. Keep `scale: 0-100`.
2. Describe the inputs for the agent in prose.
3. Declare the same inputs and the formula in the `yaml` block.
4. List the file under `metrics:` in [portal/config.yaml](../portal/config.yaml) and restart the portal.
5. Score the ideas: `.venv/bin/python portal/score_ideas.py`.

Raise `version` on every change in meaning. Editing a metric marks its stored scores as pending, and
editing `checks.md` all stored scores, so one ranking never mixes two versions.

Settings of an input:

| Setting | Meaning |
|---|---|
| `required: true` | No score while the input is unknown. |
| `default` | Value used while the input is unknown. Every input needs this or `required`. |
| `anchors` | The only allowed values. |
| `min` | Smaller values are raised to this. |
| `flag_above` | Larger values add a warning. |
| `quote_must_contain_value` | A value quoted from the idea or knowledge base must appear in the quote. |
| `estimate_is_expected` | An estimate of this input does not trigger `caps`. |
| `unit` | For readers of the file. |

The formula may use the input names, numbers, `+ - * / **`, and `log`, `log10`, `sqrt`, `min`, `max`.

The AI Act article list in `checks.md` is adapted from a2welt/ai-act-mcp `rules/ruleset.json` (MIT).
