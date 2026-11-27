# Idea Evaluation System: Architecture

Employees submit ideas through chat. Agents merge related ideas and score them. A decision team reviews the ranked list.

## 1. Overview

```mermaid
flowchart LR
    E([Employee]) <--> C[Chat interface]
    C <--> I

    subgraph A[Agent]
        I[Intake]
        M[Merge]
        S[Score]
    end

    I -->|raw idea| DB[(Idea store)]
    DB -->|raw ideas| M
    M -->|refined idea| DB
    DB -->|raw + refined| S
    S -->|score + rationale| DB

    KB[(Knowledge base)] -.->|read only| A
    F[/Metric skill file/] -.->|plugged in| S

    DB --> D[Dashboard]
    D --> T([Decision team])
```

## 2. Components

| Component | Responsibility | Reads | Writes |
|---|---|---|---|
| Chat interface | Employee submits an idea and answers follow-up questions | - | - |
| Agent: Intake | Turns the conversation into one raw idea, confirmed by the employee | Knowledge base | RawIdea |
| Agent: Merge | Finds related raw ideas of different authors and combines them into a refined idea. Runs from a dashboard button | RawIdea, RefinedIdea, knowledge base | RefinedIdea |
| Agent: Score | Fills the metric inputs for one idea at a time and answers the checks. The app calculates the score | Idea, metric, checks, knowledge base | Score |
| Idea store | Holds ideas, merge links and scores. App-generated data, in the Postgres schema `app_generated` | - | - |
| Knowledge base | Company context. Edited in `knowledge-base/`, copied to Postgres with `portal/sync_knowledge_base.py` | - | - |
| Metric skill file | Defines how ideas are judged, in `metrics/` | - | - |
| Checks file | Flags shown next to any metric: AI fit and EU AI Act screen | - | - |
| Dashboard | Lists raw and refined ideas, ranked by score, and starts Merge | Idea store | - |

## 3. Data model

Company information and app-generated data are kept apart:

| Postgres schema | Contains | Source of truth |
|---|---|---|
| `knowledge_base` | Company information: `documents`, `employees` | Files in `knowledge-base/`, copied with the sync script |
| `app_generated` | Everything the app creates: `raw_idea`, `raw_idea_history`, `score`, `refined_idea` | The database only |

The knowledge base never contains app-generated data.

```
RawIdea      { id, author_id, text, version, created_at, updated_at }
RawIdeaHistory { idea_id, version, text, saved_at }
RefinedIdea  { id, version, text, sources{raw_id: version}[2..n], rationale, differences, saved_at }
Score        { idea_id, idea_version, metric_name, metric_version, metric_sha,
               value?, rationale, details, scored_at }
```

- A raw idea starts at version 1. Its author can improve it, which raises the version. Earlier texts are kept in `raw_idea_history`.
- An improved raw idea is still a raw idea, with the same ID. Improving it never creates a refined idea.
- Only Merge creates a `RefinedIdea`, by combining two or more raw ideas of at least two authors. Each version is its own row.
- `sources` records which version of each raw idea the text was written from.
- A raw idea can feed several refined ideas.
- A score without a `value` means a required input is unknown. `details` holds the status, each input with its source and evidence, open questions and check results.
- `metric_sha` is a fingerprint of the metric and checks files. A score is current only if it, the metric version and the idea version all match.

## 4. Metric contract

The metric is a skill file that can be swapped without code changes. It is chosen in `portal/config.yaml`.

````markdown
---
name: <metric name>
version: <integer>
scale: 0-100
---
<criteria, weights and scoring instructions>

```yaml
formula: <arithmetic over the input names, giving 0-100>
inputs:
  <input name>:
    required: true        # or: default: <number>
caps: {}                  # optional limits when inputs are unknown or estimated
```
````

[metrics/README.md](metrics/README.md) lists all settings.

- **Input:** idea text and knowledge base access. No author identity: names are removed, and only `public` and `internal` documents are readable.
- **Agent output:** one value per metric input, with its source (employee, knowledge base or estimate) and evidence.
- **Output:** `{ value, rationale }`, calculated by the app from the checked inputs. `value` is empty if a required input is unknown.
- **Checks** are not part of the metric. They add flags and never change the value.

## 5. Flows

1. **Submit:** chat → Intake → employee confirms → RawIdea stored.
   **Improve:** chat → Intake reads the employee's own RawIdea → employee confirms → new version stored.
2. **Merge:** the decision team presses the dashboard button. Merge reads all raw and refined ideas without author identity. It creates a RefinedIdea, rewrites an existing one when a source is added or changed (new version), or does nothing. The app drops proposals that break these rules, and never removes a source.
3. **Score:** a submitted or changed raw idea is scored in the background, and a new or changed refined idea right after the merge. If that fails, it stays pending and can be scored from the dashboard. A refined idea is read together with the source versions it was written from, and quoted evidence must come from those sources.
4. **Metric change:** a changed metric or checks file makes all scores pending. The dashboard button or `portal/score_ideas.py` rescores them.
5. **Review:** the dashboard ranks raw and refined ideas separately by their scores under the active metric. Refined ideas list their sources.

## 6. Invariants

- Raw ideas are never edited or deleted by Merge.
- Merge runs only when a person starts it.
- Every refined idea is traceable to its source ideas.
- One ranking uses one metric version only. Ideas not yet scored under it are shown as pending.
- The agent recommends. The decision team decides.
- Intake shows an employee only knowledge base content that employee is allowed to see.
