"""Build the demo portfolio from nothing.

    python -m seed.load            rebuild everything
    python -m seed.load --keep     keep the database, re-assess only

Steps:
  1. rebuild the knowledge graph and text index from knowledge-base/
  2. load the seeded use cases
  3. load anything employee_interface has written to knowledge-base/ideas/raw/
  4. run the full assessment pipeline over all of them
  5. snapshot the ranking under the active scoring config
"""

from __future__ import annotations

import sys

from compass import db, records
from compass.agents import orchestrator
from compass.kg import ingest

from . import use_cases_a, use_cases_b

ALL_CASES = use_cases_a.CASES + use_cases_b.CASES


def load(rebuild_db: bool = True) -> None:
    if rebuild_db:
        db.reset()
    stats = ingest.rebuild()
    print(f"knowledge graph: {stats['nodes']} nodes, {stats['edges']} edges, "
          f"{stats['chunks']} text chunks")

    seeded = [records.from_seed(case) for case in ALL_CASES]
    from_interface = records.load_raw_ideas()
    if from_interface:
        print(f"employee_interface submissions found: "
              f"{', '.join(r.id for r in from_interface)}")
    everything = seeded + from_interface
    print(f"use cases: {len(seeded)} seeded + {len(from_interface)} submitted "
          f"= {len(everything)}\n")

    with db.session() as conn:
        # Store every record first, so similarity compares against the whole
        # portfolio rather than only the ideas processed before it.
        for record in everything:
            if not record.department:
                record.department = orchestrator._department_of(
                    conn, record.author_id)
            orchestrator.upsert_record(conn, record)

        results = []
        for record in everything:
            others = [r for r in everything if r.id != record.id]
            results.append(orchestrator.run(record, conn, others=others))

        ranking = orchestrator.current_ranking(conn)
        orchestrator.snapshot(conn, db.get_active_scoring(conn), ranking)

    _report(results, ranking)


def _report(results: list[dict], ranking: list[dict]) -> None:
    def count(key: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for item in results:
            out[str(item[key])] = out.get(str(item[key]), 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    print("AI fit:      ", count("ai_fit"))
    print("Risk:        ", count("risk"))
    print("Feasibility: ", count("feasibility"))
    scored = [r for r in results if r["score"] is not None]
    print(f"Scored:       {len(scored)} of {len(results)}; "
          f"blocked from selection: "
          f"{sum(1 for r in results if not r['selectable'])}")
    costs = [r["est_cost_eur"] for r in results if r["est_cost_eur"]]
    print(f"Cost range:   EUR {min(costs):,} to EUR {max(costs):,}")
    print(f"Overlap links suggested: {sum(r['overlaps'] for r in results)}")

    print("\nTop 10 by score:")
    for entry in ranking[:10]:
        print(f"  {entry['rank']:>2}. {entry['score']:>5}  "
              f"{entry['use_case_id']}  {entry['title'][:52]}")

    blocked = [r for r in results if not r["selectable"]]
    print(f"\nBlocked from selection ({len(blocked)}):")
    for item in blocked[:12]:
        print(f"  {item['id']}  {item['title'][:44]:<44} {item['gate_reason'][:64]}")


if __name__ == "__main__":
    load(rebuild_db="--keep" not in sys.argv)
