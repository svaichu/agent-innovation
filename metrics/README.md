# Metrics

Skill files used by the Score agent. Code is in [portal/](../portal/); the contract is in
[ARCHITECTURE.md](../ARCHITECTURE.md#4-metric-contract).

| File | What it is |
|---|---|
| `rice.md` | The metric: RICE business value, with its inputs, anchors and formula. |
| `checks.md` | Flags shown next to any metric: AI / conventional automation / more research, and a preliminary EU AI Act screen. |

## Add or change a metric

1. Copy `rice.md`. Set `name` and `version`, keep `scale: 0-100`.
2. Describe the inputs for the agent in prose.
3. Declare the same inputs and the formula in the `yaml` block.
4. Set `metric:` in [portal/config.yaml](../portal/config.yaml).
5. Score the ideas again: `.venv/bin/python portal/score_ideas.py`.

Raise `version` on every change in meaning. Editing the metric or `checks.md` marks stored scores as
pending, so one ranking never mixes two versions.

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
