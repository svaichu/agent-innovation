# Idea Portal

Collect improvement ideas from employees through a short chat, and give the innovation team one place to review them.

Suggestion boxes tend to fill up with one-line ideas that nobody can judge. Here an intake agent asks follow-up questions until an idea says what happens today, what is wrong with it and what should change. The employee checks the draft and decides whether to submit it.

> The example company, **Brambleworks GmbH**, and all of its people, customers and figures are invented for testing and demonstration.

## How it works

1. **Log in.** Employees get the chat. The innovation team gets the dashboard.
2. **Describe the idea.** The agent asks one short question at a time, in the employee's language.
3. **Check the draft.** When nothing is missing, the agent shows the complete idea.
4. **Submit.** Only the "Submit idea" button stores it, under an ID such as `RI-0001`.
5. **Improve.** Employees can ask the agent to show their submitted ideas and change one. The "Update idea" button saves the new version under the same ID, and earlier versions are kept.
6. **Score.** Every new or changed idea is scored in the background. Employees do not see the score.
7. **Merge.** The **Merge related ideas** button combines related ideas of different employees into refined ideas, and scores them.
8. **Review.** The dashboard ranks submitted and refined ideas by score, each in its own tab, and shows their reasons, flags, authors and departments. Ideas can be searched, filtered and sorted.

A complete idea covers:

| Field | Question it answers |
|---|---|
| Scope | Is it a company process or the employee's own workflow? |
| Current process | How does it work today? |
| Problem | What is wrong with that? |
| Proposed improvement | What should change? |
| Who is affected | Whose work does this touch? |
| Expected benefit | What gets better, for example time saved or fewer errors? |

### Scoring

The score agent reads the idea and the knowledge base and fills in the inputs of the metric. The app checks the evidence and calculates the score.

| Result | Meaning |
|---|---|
| Score 0-100 | [RICE](metrics/rice.md): reach, impact, confidence and effort |
| Needs information | Reach or effort is neither stated nor inferable. The dashboard lists the open questions. |
| AI fit | AI, conventional automation, or more research |
| EU AI Act | Preliminary risk tier and transparency duties, not legal advice |

- **Evidence is checked.** A quote must exist in the idea or in a readable document, and a quoted reach must contain the number. Estimates are labelled, and their reasoning is not verified.
- **Flags never change the score** ([checks.md](metrics/checks.md)).
- **No author identity.** Names are removed from the idea and the documents before the agent reads them. It cannot read confidential documents or the employee list.
- **The metric is swappable.** Inputs and formula are declared in the [metric file](metrics/README.md).

Ideas are scored again with:

```bash
.venv/bin/python portal/score_ideas.py             # every pending idea
.venv/bin/python portal/score_ideas.py RI-0001     # one idea, even if scored
.venv/bin/python portal/score_ideas.py --all       # every idea again
```

The **Score pending ideas** button on the dashboard does the same as the first command.

### Merging

The merge agent runs only when the innovation team presses **Merge related ideas**. It reads all ideas, groups those that one solution would address, and writes a refined idea for each group. Refined ideas get IDs such as `RF-0001` and have their own tab on the dashboard.

- **At least two people.** Ideas of a single author are never merged.
- **Ideas stay as they are.** Every refined idea lists the ideas it came from. Contradictions and open points between them are shown under "Why merged".
- **Pressing again is safe.** A refined idea gets a new version only if a source was added or edited. Edited sources are marked "Changed since merge" until then. Earlier versions are kept in the database.
- **No author identity.** The agent sees only whether two ideas come from the same person, and names are removed from the texts.
- **Ranked like other ideas.** Refined ideas are scored with the same metric and ranked in their own tab. Quotes used as evidence must come from the source ideas, not from the merged text.

### Design choices

- **The employee stays in control.** The agent cannot submit or change anything. It can only propose a draft.
- **Own ideas only.** The agent can read only the ideas of the logged-in employee.
- **No invented details.** The agent is instructed to use only what the employee said, and to record the rest as unknown.
- **No judging at intake.** Collecting an idea and scoring it are kept separate.
- **The author comes from the login**, so it cannot be chosen in the chat.
- **Company data and app data stay apart**, in two Postgres schemas.

## Status

| Part | State |
|---|---|
| Intake chat | Working |
| Viewing and improving submitted ideas | Working |
| Innovation Dashboard (raw ideas and their authors) | Working |
| Knowledge base sync to Postgres | Working |
| Agents reading the knowledge base | Score and merge agents |
| Merging related ideas | Working, from a dashboard button |
| Scoring with a swappable metric, and ranked lists | Working for raw and refined ideas |

## Architecture

```mermaid
flowchart LR
    E([Employee]) <--> C[Chat page]
    C <--> I[Intake agent]
    I -->|draft| C
    C -->|Submit button| DB[(Postgres<br/>app_generated)]
    DB -->|new, changed or merged idea| S[Score agent]
    M[/Metric file/] --> S
    S -->|score + reasons| DB
    DB --> D[Innovation Dashboard]
    D -->|Merge button| R[Merge agent]
    R -->|refined idea| DB
    D --> T([Innovation team])

    F[knowledge-base/ files] -->|sync script| KB[(Postgres<br/>knowledge_base)]
    KB -.->|employee names| C
    KB -.->|authors| D
    KB -.->|read only| S
    KB -.->|read only| R
```

The diagram shows what is built today. [ARCHITECTURE.md](ARCHITECTURE.md) describes the full target design.

Built with [Gradio](https://www.gradio.app/), the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) and PostgreSQL.

## Getting started

### Requirements

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/)
- A PostgreSQL database
- An OpenAI API key

### 1. Install

```bash
git clone https://github.com/svaichu/agent-innovation.git
cd agent-innovation
uv sync
```

### 2. Configure

Create `.env` in the project root with your database connection string, without quotes:

```ini
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

Set the OpenAI key in your shell. The portal does not read it from `.env`.

```bash
export OPENAI_API_KEY=your-key
```

Create `portal/users.csv` with one row per login:

```csv
username,password
innovation,choose-a-password
vogel,choose-another-password
```

- `innovation` opens the dashboard.
- An employee's username is their last name in lowercase, as listed in [employees.csv](knowledge-base/people/employees.csv). A last name shared by two employees cannot log in.

Both `.env` and `portal/users.csv` are ignored by git.

The models of the agents and the active metric are set in [config.yaml](portal/config.yaml).

### 3. Load the knowledge base

```bash
.venv/bin/python portal/sync_knowledge_base.py --dry-run   # show what would change
.venv/bin/python portal/sync_knowledge_base.py             # create the tables and copy the files
```

The sync goes one way: local files replace what is in the `knowledge_base` schema. Submitted ideas are not touched. Run it again after editing the knowledge base.

### 4. Run

```bash
.venv/bin/python portal/app.py
```

Open the address printed in the terminal, by default <http://127.0.0.1:7860>. The bottom of the login page shows when the running code was last committed.

## Project layout

```
portal/
  app.py                    Entry point: login and page selection
  employee_interface.py     Chat page and intake agent
  intake_prompt.md          Instructions for the intake agent
  innovation_dashboard.py   Dashboard page
  idea_store.py             Idea format, saving and listing
  score_ideas.py            Scores ideas: after submit, from the dashboard or the shell
  score_agent.py            The score agent, which fills the metric inputs
  score_prompt.md           Instructions for the score agent
  scoring.py                Checks evidence and calculates the metric
  checks.py                 AI fit and EU AI Act flags
  merge_ideas.py            Merges related ideas and checks what the agent proposes
  merge_agent.py            The merge agent, which writes refined ideas
  merge_prompt.md           Instructions for the merge agent
  refined_store.py          Stored refined ideas
  knowledge.py              What the score and merge agents may read
  score_store.py            Stored scores
  auth.py                   Login check
  db.py                     Database connection and tables
  sync_knowledge_base.py    Copies knowledge-base/ to Postgres
  config.yaml               Models and the active metric
  theme.py                  Colours, styles and the login page
knowledge-base/             Example company: people, products, processes, policies
metrics/                    Metric and checks files
tests/                      Scoring and merge tests
ARCHITECTURE.md             Target design
```

See the [knowledge base index](knowledge-base/README.md) for the company content.

## Tests

```bash
.venv/bin/python -m unittest discover tests
```

They cover scoring, evidence checks, flags, ranking and which merges are stored, without a database or API key.

## Limitations

This is a prototype. Before using it with real data:

- **Login is minimal.** Passwords are stored in plain text in `users.csv`.
- **Chats leave your network.** Messages are sent to the OpenAI API, and the Agents SDK uploads traces to OpenAI unless tracing is turned off.
- **Personal data is not filtered.** The agent asks employees to leave it out, but nothing enforces that.
- **Scores vary between runs.** The calculation is fixed, but a model fills the inputs.
- **Many ideas need information.** Intake does not ask for volumes or effort.
- **Flags rest on unverified model answers.** A person has to confirm them.
- **Merges rest on the model's judgement.** The app checks the sources and authors, not whether the ideas really belong together or the text is faithful to them.
- **A merge reads all ideas at once.** This suits tens of ideas, not thousands.
- **Only the scoring and merge rules have automated tests.**
