# AI Compass

**Many ideas. One budget. Which AI ideas deliver value?**

Cognita Reply's challenge from *AI Connect: Research Meets Industry*, Aachen,
26–27 November 2026. An employee describes an idea in a chat. An agent turns it
into a consistent record, checks whether AI is even the right tool, screens it
against the EU AI Act, works out whether this company could actually deliver
it, scores it, and puts it on a ranked board that four people are allowed to
see.

**The agent recommends. People decide.**

Everything here is fictional: Brambleworks GmbH, its 120 employees, its
customers and every figure.

---

## Run it

Python 3.11+ and Node are not both needed — this is Python only.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python seed/generate_people.py       # 120-person roster
.venv/bin/python seed/generate_docs.py         # directory + org chart
.venv/bin/python seed/generate_departments.py  # nine department pages
.venv/bin/python seed/generate_logins.py       # demo credentials
.venv/bin/python -m seed.load                  # graph + assess the portfolio

.venv/bin/python -m compass.serve              # BOTH apps -> :7860
```

That serves the board at `/` and the idea-intake chat at `/intake/`, on one
port behind **one login** — sign in once and both work. `/healthz` reports
whether the intake app loaded.

The two can still be run separately if you prefer:

```bash
.venv/bin/python -m compass.app                # board  -> :7861
.venv/bin/python employee_interface/app.py     # intake -> :7860
```

`seed/generate_logins.py` prints the credentials to use on stage. The four
admin logins are the only ones that see the assessed portfolio.

### With and without an API key

**It runs with no API key at all**, on a deterministic rule engine - regex for
the numbers, keyword tiers for the judgements, knowledge-graph queries for the
facts, and the arithmetic in the YAML config. That is honest engineering but it
is **not** a model: with no key, nothing in the pipeline is doing reading
comprehension. The dashboard says which engine produced each verdict.

To use a model, copy `.env.example` to `.env` (gitignored) and fill in one
provider:

```bash
cp .env.example .env            # then edit it
.venv/bin/python -m compass.llm # ONE test call - checks the key works
.venv/bin/python -m seed.load   # re-assess all 43 ideas
```

An exported `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` also works and takes
precedence over `.env`.

**Note on Anthropic keys:** API access comes from
[console.anthropic.com](https://console.anthropic.com) and is billed against
prepaid credits. A Claude Pro or Max subscription does **not** include it.

What the model is used for, and what never needs one:

| Step | With a key | Without a key |
|---|---|---|
| Similarity | Judges each shortlisted pair | TF-IDF cosine + capability tags |
| AI fit | Reads the idea, weighs AI vs. automation | Keyword sets |
| EU AI Act | Reasons over the Act, quotes the submitter | Keyword decision tree |
| Feasibility | Names required skills, systems, data, effort | Keyword hints + regex |
| Score | Extracts reach, judges impact, rates evidence | Regex + keyword tiers |
| **Feasibility arithmetic, the risk gate, classification filtering, the RICE formula** | **graph queries and config** | **identical** |

Roughly 5-8 calls per idea, so about 300 for the full portfolio, with short
prompts. Effort defaults to `low` because these are extraction and
classification tasks rather than open-ended reasoning; raise it with
`COMPASS_EFFORT` if a verdict looks shallow.

The offline engine is insurance, not a feature. Its verdicts are correct and
conservative; its prose is visibly thinner, and the knowledge chatbot quotes
sections rather than composing an answer. A rate limit mid-pitch cannot end
the demo.

---

## The demo, in order

Log in to the board as **E26 (Ottilie Janssens, Head of Strategy & AI
Portfolio)** — the admin who owns this tool.

| # | What to show | Where |
|---|---|---|
| 1 | **Duplicate across departments.** UC-001 (Sales: answer tender questions) and UC-002 (Support: answer repeat tickets) are linked. Different words, same machine: search our own documents and draft text for a human to approve. Neither team knew. | Portfolio → select UC-001 → *Related ideas* |
| 2 | **Conventional automation wins.** UC-003 wants to stop retyping HubSpot orders into the inventory spreadsheet. Verdict: `conventional automation`, citing `it/systems.md` — "No integration between HubSpot, the inventory spreadsheet and DATEV". And it is **not** feasible yet, because that spreadsheet has no API. | Portfolio → UC-003 |
| 3 | **A promising AI case, ranked and screened.** UC-004 routes 1,250 tickets a month. High score, feasible, minimal risk — with the Article 50 transparency flag in its own column because a drafted reply reaches a customer. | Portfolio → UC-004 |
| 4 | **An incomplete idea gets questions, not guesses.** UC-005 is "use AI for our content somehow". 0 of 8 fields usable, no risk verdict, not scored, and four questions assigned back to the author. | Portfolio → UC-005, then Review queue |
| 5 | **Change the criteria, watch the ranking move.** Switch to `rice-v2-cost-weighted`. Around 23 ideas move and each row says which factor changed and why. | Scoring method |

Then the two that make the risk lane real:

- **UC-006** "spot stressed colleagues from their webcam" → **prohibited**,
  Article 5(1)(f). Press **Select**: it refuses, and says the business score
  does not override it.
- **UC-007** "rank incoming applications" → **high-risk**, Article 6(2) with
  Annex III point 4(a), blocked pending review by E113 and E110. Company policy
  forbids it independently, and the decision log already recorded that on
  2026-09-21.

And the join with the intake app:

- Submit an idea at `:7860` as **E17**. It lands as `RI-NNNN.md`, and after
  `python -m seed.load` it appears on the board at **4/8 fields** — scored, but
  blocked from selection because the risk screening is incomplete, with the
  four missing fields assigned back to E17 by name. That is the designed
  behaviour, not a bug: see `compass/proposals/idea-draft-8-fields.md`.

Finally, log in as **E17** to see that the portfolio tab is simply not there,
and that `My ideas` shows status without scores. **Log out** is top right in
both apps; it ends only the current browser session, so you can keep an admin
view open in one tab and an employee view in another and compare them.

---

## How it works

```
employee_interface/ (Gradio + OpenAI Agents SDK)   ← a teammate's app
    └── writes knowledge-base/ideas/raw/RI-NNNN.md

compass/
    records.py    the 8-field core record; adapters from raw files and seeds
    kg/ingest.py  knowledge base → 465 nodes, 769 edges, 163 text chunks
    kg/query.py   the only facts feasibility may use, each with a citation
    kg/retrieve.py classification-filtered text search
    llm.py        OpenAI | Anthropic | offline rules, with fallback
    agents/       similarity → ai_fit → risk → feasibility → score
    views.py      data assembly and the access rules
    app.py        the dashboard
config/           the questionnaire, two scoring configs, the AI Act tree
seed/             the 120-person company and 42 seeded ideas
evals/            14 labelled behaviour checks
```

Two storage decisions worth knowing:

- **Raw ideas stay as markdown files** under `knowledge-base/ideas/raw/`. They
  are the employee's own words and stay greppable and auditable.
- **Everything else lives in `compass.db`** and is regenerable. Delete it and
  run `python -m seed.load`; no employee input is lost.

### Where the rules live, not the code

| What | File |
|---|---|
| The 8 core fields, why each exists, which agent consumes it, follow-up triggers | `config/intake-questionnaire.yaml` |
| RICE scales, bands, Confidence caps | `config/scoring/rice-v1.yaml` |
| Cost-weighted variant for when budget binds | `config/scoring/rice-v2-cost-weighted.yaml` |
| Article 5 / Article 6 + Annex I,III / Article 50, with citations | `config/risk/eu-ai-act.yaml` |

`consumed_by` in the questionnaire is the part to read. It is how the intake
chat knows *which* facts to collect: `deployment_context` exists because
Article 50 cannot be decided without it, `effort` because it is the RICE
divisor.

### Two rules enforced in code, not prose

**Risk never loses to score.** `compass/agents/risk.py:gate()` decides whether
an idea can be selected and never sees the score. `views.record_decision`
calls it before writing anything.

**Nothing is invented.** A field the submitter did not give is `missing`, not
inferred. The risk screening cannot return `minimal` while a field it needs is
absent — it returns `insufficient_information` and raises a review item. The
feasibility agent may estimate effort, but the estimate is labelled as the
agent's and flagged for confirmation.

---

## Checks

```bash
.venv/bin/python -m evals.run_evals        # 14 labelled checks, all passing
.venv/bin/python -m compass.kg.query       # graph lookups
.venv/bin/python -m compass.kg.retrieve    # retrieval, per role
```

The evals assert behaviour the brief requires: conventional automation is not
called AI, Article 5(1)(f) fires on workplace emotion inference, candidate
ranking lands on Annex III point 4(a), ticket routing stays minimal rather than
being over-flagged, an empty idea produces questions, the cross-department
duplicate is linked, a config change moves the ranking with an explanation for
every move, and an employee's retrieval returns no confidential page.

---

## Limits — state these in the pitch

- **The EU AI Act screening is preliminary triage, not legal advice.** It
  flags and cites; a qualified person decides. Every non-minimal verdict is
  routed to E113 (Data Protection Officer) and E110 (Head of Quality &
  Regulatory).
- **Demo authentication is not authentication.** `seed/data/demo_logins.csv`
  holds plain-text passwords for localhost, is gitignored, and would be an SSO
  integration in anything real. Authorization, by contrast, *is* enforced
  server-side in `compass/views.py`.
- **Offline verdicts are keyword rules.** They are deliberately conservative
  and get the demo scenarios right, but they are not a substitute for a model.
  Thresholds in `similarity.py` were tuned on this 42-idea portfolio and would
  need retuning on real data.
- **RICE inputs are self-reported.** Confidence is the honesty dial: a guess
  is published with low Confidence rather than being quietly rounded up.
- **One fictional company.** The questionnaire has a per-client `extensions`
  block and the scoring is a config file, but multi-tenancy is untested.
- **Overlap detection combines lexical similarity with capability signatures.**
  Pure TF-IDF missed the headline duplicate pair (cosine 0.15, because
  "tenders" and "tickets" share no words). Embeddings would do this better and
  are the obvious next step.
