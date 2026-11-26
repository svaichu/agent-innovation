# Idea Portal

Collect improvement ideas from employees through a short chat, and give the innovation team one place to review them.

Suggestion boxes tend to fill up with one-line ideas that nobody can judge. Here an intake agent asks follow-up questions until an idea says what happens today, what is wrong with it and what should change. The employee checks the draft and decides whether to submit it.

> The example company, **Brambleworks GmbH**, and all of its people, customers and figures are invented for testing and demonstration.

## How it works

1. **Log in.** Employees get the chat. The innovation team gets the dashboard.
2. **Describe the idea.** The agent asks one short question at a time, in the employee's language.
3. **Check the draft.** When nothing is missing, the agent shows the complete idea.
4. **Submit.** Only the "Submit idea" button stores it, under an ID such as `RI-0001`.
5. **Review.** The dashboard lists every idea, newest first, with its author and department.

A complete idea covers:

| Field | Question it answers |
|---|---|
| Scope | Is it a company process or the employee's own workflow? |
| Current process | How does it work today? |
| Problem | What is wrong with that? |
| Proposed improvement | What should change? |
| Who is affected | Whose work does this touch? |
| Expected benefit | What gets better, for example time saved or fewer errors? |

### Design choices

- **The employee stays in control.** The agent cannot submit anything. It can only propose a draft.
- **No invented details.** The agent is instructed to use only what the employee said, and to record the rest as unknown.
- **No judging at intake.** Collecting an idea and scoring it are kept separate.
- **The author comes from the login**, so it cannot be chosen in the chat.
- **Company data and app data stay apart**, in two Postgres schemas.

## Status

| Part | State |
|---|---|
| Intake chat | Working |
| Innovation Dashboard (raw ideas and their authors) | Working |
| Knowledge base sync to Postgres | Working |
| Agents reading the knowledge base | Planned |
| Merging related ideas | Planned |
| Scoring with a swappable metric, and a ranked list | Planned |

## Architecture

```mermaid
flowchart LR
    E([Employee]) <--> C[Chat page]
    C <--> I[Intake agent]
    I -->|draft| C
    C -->|Submit button| DB[(Postgres<br/>app_generated)]
    DB --> D[Innovation Dashboard]
    D --> T([Innovation team])

    F[knowledge-base/ files] -->|sync script| KB[(Postgres<br/>knowledge_base)]
    KB -.->|employee names| C
    KB -.->|authors| D
```

The diagram shows what is built today. [ARCHITECTURE.md](ARCHITECTURE.md) describes the full target design, including the merge and score agents.

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

The model used by the intake agent is set in [config.yaml](portal/config.yaml).

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
  auth.py                   Login check
  db.py                     Database connection and tables
  sync_knowledge_base.py    Copies knowledge-base/ to Postgres
  config.yaml               Model settings
knowledge-base/             Example company: people, products, processes, policies
ARCHITECTURE.md             Target design
```

See the [knowledge base index](knowledge-base/README.md) for the company content.

## Limitations

This is a prototype. Before using it with real data:

- **Login is minimal.** Passwords are stored in plain text in `users.csv`.
- **Chats leave your network.** Messages are sent to the OpenAI API, and the Agents SDK uploads traces to OpenAI unless tracing is turned off.
- **Personal data is not filtered.** The agent asks employees to leave it out, but nothing enforces that.
- **There are no automated tests yet.**
