# Metrics

The **Score** step of [ARCHITECTURE.md](../ARCHITECTURE.md): the Score agent reads a raw idea and the
knowledge base and fills the inputs of the metric files; `scoring.py` turns them into a 0-100 score and flags.
Same inputs give the same output; editing the scales in a metric file re-ranks all ideas.

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -r employee_interface/requirements.txt
```

## Usage

```bash
.venv/bin/python metrics/test_scoring.py
.venv/bin/python metrics/test_score_agent.py
.venv/bin/python metrics/scoring.py                                          # ranks the example ideas, no API key
OPENAI_API_KEY=... .venv/bin/python metrics/score_agent.py knowledge-base/ideas/raw/RI-0001.md
```

## Layout

| File | What it is |
|---|---|
| `rice.md` | Business value: RICE inputs, where each comes from (employee, knowledge base, estimate), scales, cap. |
| `checks.md` | Flags, not a score: AI / conventional automation / more research, and a preliminary EU AI Act screen. |
| `scoring.py` | Turns filled inputs into score, AI-fit label, AI Act tier, citations and `review_required`. |
| `score_agent.py` | The Score agent (openai-agents) with tools to read the knowledge base; returns the `Score` record plus checks. |
| `examples/ideas.json` | 8 fictional Brambleworks ideas covering the demo cases. |
| `test_*.py` | Runnable checks, no API key needed. |

When the employee gives no numbers, the agent looks them up in the knowledge base or estimates them from
cited company facts; estimates lower confidence to 0.5. Numbers quoted from the idea are the employee's own
claims. Ideas mentioning risk terms always go to review. The Score record is for the decision team, not the
employee. AI Act results are a preliminary screening, not legal advice.
