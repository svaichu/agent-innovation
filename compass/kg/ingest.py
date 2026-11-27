"""Build the knowledge graph and the text index from the knowledge base.

Everything here is deterministic parsing - no model involved. The graph is what
lets the feasibility agent answer "can we do this?" with cited facts instead of
an opinion, and the chunk table is what lets the knowledge chatbot answer
questions with a source path and the right classification.

Run: python -m compass.kg.ingest
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path

from .. import config, db

KB = config.KNOWLEDGE_BASE


# --------------------------------------------------------------------------- #
# parsing helpers
# --------------------------------------------------------------------------- #
def read_front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    return meta


def markdown_tables(text: str) -> list[list[dict[str, str]]]:
    """Every pipe table in a markdown document, as lists of row dicts."""
    tables: list[list[dict[str, str]]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if not lines[index].strip().startswith("|"):
            index += 1
            continue
        header = [c.strip() for c in lines[index].strip().strip("|").split("|")]
        if index + 1 >= len(lines) or not re.match(
            r"^\|[\s:|-]+\|?$", lines[index + 1].strip()
        ):
            index += 1
            continue
        rows = []
        cursor = index + 2
        while cursor < len(lines) and lines[cursor].strip().startswith("|"):
            cells = [c.strip() for c in lines[cursor].strip().strip("|").split("|")]
            if len(cells) == len(header):
                rows.append(dict(zip(header, cells)))
            cursor += 1
        if rows:
            tables.append(rows)
        index = cursor
    return tables


def section_text(text: str, heading: str) -> str:
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def bullet_list(block: str) -> list[str]:
    return [re.sub(r"^[-*]\s+", "", line).strip()
            for line in block.splitlines()
            if line.strip().startswith(("-", "*"))]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def money(text: str) -> int | None:
    """First EUR amount in a string, in whole euros."""
    cleaned = text.replace(",", "").replace(".", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*million", text, re.IGNORECASE)
    if match:
        return int(float(match.group(1)) * 1_000_000)
    match = re.search(r"(?:EUR|€)\s*(\d[\d\s]*)", cleaned)
    if match:
        return int(match.group(1).replace(" ", ""))
    match = re.search(r"\b(\d{4,})\b", cleaned)
    return int(match.group(1)) if match else None


# --------------------------------------------------------------------------- #
# graph writers
# --------------------------------------------------------------------------- #
class Graph:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.nodes = 0
        self.edges = 0

    def node(self, node_id: str, node_type: str, name: str,
             attrs: dict | None = None, classification: str = "internal",
             source_path: str = "") -> str:
        self.conn.execute(
            "INSERT INTO kg_node (id, type, name, attrs, classification, source_path) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
            "attrs = excluded.attrs, name = excluded.name, "
            "classification = excluded.classification, "
            "source_path = excluded.source_path",
            (node_id, node_type, name,
             json.dumps(attrs or {}, ensure_ascii=False),
             classification, source_path),
        )
        self.nodes += 1
        return node_id

    def edge(self, src: str, rel: str, dst: str, attrs: dict | None = None) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO kg_edge (src, rel, dst, attrs) VALUES (?, ?, ?, ?)",
            (src, rel, dst, json.dumps(attrs or {}, ensure_ascii=False)),
        )
        self.edges += 1


def ingest_people(graph: Graph) -> None:
    employees = list(csv.DictReader(
        (KB / "people" / "employees.csv").open(encoding="utf-8")))
    capacity = {r["employee_id"]: r for r in csv.DictReader(
        (KB / "people" / "capacity.csv").open(encoding="utf-8"))}

    for row in employees:
        cap = capacity.get(row["id"], {})
        node_id = f"employee:{row['id']}"
        graph.node(
            node_id, "Employee", row["name"],
            attrs={
                "employee_id": row["id"],
                "role": row["role"],
                "department": row["department"],
                "work_mode": row["work_mode"],
                "start_date": row["start_date"],
                "responsibilities": row["responsibilities"],
                "site": cap.get("site", ""),
                "seniority": cap.get("seniority", ""),
                "fte": cap.get("fte", "1.0"),
                "capacity_pct_available": int(cap.get("capacity_pct_available", 0) or 0),
                "cost_per_day_eur": int(cap.get("cost_per_day_eur", 0) or 0),
                "access_role": cap.get("access_role", "employee"),
            },
            source_path="knowledge-base/people/employees.csv",
        )
        graph.edge(node_id, "member_of", f"department:{row['department']}")
        if cap.get("site"):
            graph.edge(node_id, "located_at", f"site:{slug(cap['site'])}")
        if row["manager_id"]:
            graph.edge(node_id, "reports_to", f"employee:{row['manager_id']}")
        for skill in (s.strip() for s in row["skills"].split(";") if s.strip()):
            skill_id = f"skill:{slug(skill)}"
            graph.node(skill_id, "Skill", skill)
            graph.edge(node_id, "has_skill", skill_id)

    for site in {c.get("site") for c in capacity.values() if c.get("site")}:
        graph.node(f"site:{slug(site)}", "Site", site)


def ingest_departments(graph: Graph) -> None:
    for path in sorted((KB / "departments").glob("*.md")):
        meta = read_front_matter(path)
        text = path.read_text(encoding="utf-8")
        key = path.stem
        source = f"knowledge-base/departments/{path.name}"
        node_id = f"department:{key}"

        figures = {}
        for table in markdown_tables(text):
            if table and "Measure" in table[0]:
                figures = {r["Measure"]: {"current": r.get("Current", ""),
                                          "target": r.get("Target", "")}
                           for r in table}
        graph.node(
            node_id, "Department", meta.get("title", key),
            attrs={"key": key, "owner": meta.get("owner", ""),
                   "mission": section_text(text, "Mission"),
                   "tools": section_text(text, "Tools"),
                   "figures": figures},
            classification=meta.get("classification", "internal"),
            source_path=source,
        )
        if meta.get("owner"):
            graph.edge(f"employee:{meta['owner']}", "owns", node_id)

        for index, pain in enumerate(bullet_list(section_text(text, "Known pain points")), 1):
            pain_id = f"pain:{key}-{index:02d}"
            graph.node(pain_id, "PainPoint", pain,
                       attrs={"department": key}, source_path=source)
            graph.edge(node_id, "suffers", pain_id)


def ingest_systems(graph: Graph) -> None:
    source = "knowledge-base/it/systems.csv"
    for row in csv.DictReader((KB / "it" / "systems.csv").open(encoding="utf-8")):
        node_id = f"system:{slug(row['system'])}"
        graph.node(
            node_id, "System", row["system"],
            attrs={
                "purpose": row["purpose"],
                "owner_id": row["owner_id"],
                "personal_data": row["personal_data"],
                "api_or_automation": row["api_or_automation"],
                "in_data_warehouse": row.get("in_data_warehouse", "no"),
                # The single most useful derived fact for feasibility.
                "integrable": row["api_or_automation"] in ("yes", "export only"),
            },
            source_path=source,
        )
        if row["owner_id"]:
            graph.edge(f"employee:{row['owner_id']}", "owns", node_id)


def ingest_datasets(graph: Graph) -> None:
    source = "knowledge-base/it/data-inventory.csv"
    for row in csv.DictReader(
        (KB / "it" / "data-inventory.csv").open(encoding="utf-8")
    ):
        node_id = f"dataset:{slug(row['dataset'])}"
        quality = row["quality"].split(":")[0].strip()
        graph.node(
            node_id, "Dataset", row["dataset"],
            attrs={
                "system": row["system"],
                "owner_id": row["owner_id"],
                "volume": row["volume"],
                "quality": quality,
                "quality_note": row["quality"],
                "personal_data": row["personal_data"],
                "usable_as_is": quality.startswith("high"),
            },
            source_path=source,
        )
        if row["owner_id"]:
            graph.edge(f"employee:{row['owner_id']}", "owns", node_id)
        system_id = f"system:{slug(row['system'])}"
        if graph.conn.execute("SELECT 1 FROM kg_node WHERE id = ?",
                              (system_id,)).fetchone():
            graph.edge(system_id, "stores_dataset", node_id)


def ingest_strategy(graph: Graph) -> None:
    path = KB / "company" / "strategy-2027.md"
    meta = read_front_matter(path)
    text = path.read_text(encoding="utf-8")
    source = "knowledge-base/company/strategy-2027.md"
    classification = meta.get("classification", "confidential")

    for table in markdown_tables(text):
        header = set(table[0])
        if {"Priority", "Owner"} <= header:
            for row in table:
                node_id = f"priority:{row['#']}"
                graph.node(node_id, "StrategyPriority", row["Priority"],
                           attrs={"target": row.get("Target by end of 2027", ""),
                                  "owner": row.get("Owner", "")},
                           classification=classification, source_path=source)
                owner = re.search(r"\((E\d+)\)", row.get("Owner", ""))
                if owner:
                    graph.edge(f"employee:{owner.group(1)}", "owns", node_id)
        elif {"Constraint", "Value"} <= header:
            for row in table:
                node_id = f"constraint:{slug(row['Constraint'])}"
                graph.node(node_id, "Constraint", row["Constraint"],
                           attrs={"value": row["Value"],
                                  "amount_eur": money(row["Value"])},
                           classification=classification, source_path=source)


def ingest_projects(graph: Graph) -> None:
    path = KB / "projects" / "active-projects.md"
    source = "knowledge-base/projects/active-projects.md"
    text = path.read_text(encoding="utf-8")
    for table in markdown_tables(text):
        if not table or "Project" not in table[0]:
            continue
        for row in table:
            node_id = f"project:{row['ID']}"
            effort = re.search(r"(\d+)", row.get("Remaining effort", ""))
            graph.node(
                node_id, "Project", row["Project"],
                attrs={"lead": row.get("Lead", ""), "status": row.get("Status", ""),
                       "due": row.get("Due", ""),
                       "remaining_person_days": int(effort.group(1)) if effort else None,
                       "members": row.get("Members", "")},
                source_path=source,
            )
            if row.get("Lead"):
                graph.edge(f"employee:{row['Lead']}", "leads", node_id)


def ingest_policies_and_processes(graph: Graph) -> None:
    for folder, node_type in (("policies", "Policy"), ("processes", "Process")):
        for path in sorted((KB / folder).glob("*.md")):
            meta = read_front_matter(path)
            graph.node(
                f"{node_type.lower()}:{path.stem}", node_type,
                meta.get("title", path.stem),
                attrs={"owner": meta.get("owner", "")},
                classification=meta.get("classification", "internal"),
                source_path=f"knowledge-base/{folder}/{path.name}",
            )


def ingest_decisions(graph: Graph) -> None:
    path = KB / "projects" / "decision-log.md"
    source = "knowledge-base/projects/decision-log.md"
    for table in markdown_tables(path.read_text(encoding="utf-8")):
        if not table or "Decision" not in table[0]:
            continue
        for row in table:
            graph.node(
                f"decision:{slug(row['Date'] + '-' + row['Decision'][:30])}",
                "Decision", row["Decision"],
                attrs={"date": row["Date"], "reason": row.get("Reason", ""),
                       "decided_by": row.get("Decided by", "")},
                source_path=source,
            )


# --------------------------------------------------------------------------- #
# text chunks for retrieval
# --------------------------------------------------------------------------- #
def ingest_chunks(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM kb_chunk")
    if db.has_fts(conn):
        conn.execute("DELETE FROM kb_chunk_fts")

    count = 0
    for path in sorted(KB.rglob("*.md")):
        # Raw ideas are submissions, not company facts. Keeping them out of the
        # knowledge chatbot's index stops one employee's idea being answered
        # back to another as though it were policy.
        if "ideas" in path.parts:
            continue
        meta = read_front_matter(path)
        classification = meta.get("classification", "internal")
        relative = str(path.relative_to(config.ROOT))
        text = path.read_text(encoding="utf-8")
        _, _, body = text.partition("---\n")
        _, _, body = body.partition("---\n")

        blocks = re.split(r"^(##\s+.+)$", body, flags=re.MULTILINE)
        preamble = blocks[0].strip()
        if preamble:
            conn.execute(
                "INSERT INTO kb_chunk (source_path, heading, text, classification) "
                "VALUES (?, ?, ?, ?)",
                (relative, meta.get("title", path.stem), preamble, classification),
            )
            count += 1
        for index in range(1, len(blocks) - 1, 2):
            heading = blocks[index].lstrip("# ").strip()
            chunk = blocks[index + 1].strip()
            if not chunk:
                continue
            conn.execute(
                "INSERT INTO kb_chunk (source_path, heading, text, classification) "
                "VALUES (?, ?, ?, ?)",
                (relative, heading, chunk, classification),
            )
            count += 1

    if db.has_fts(conn):
        conn.execute(
            "INSERT INTO kb_chunk_fts (rowid, text, heading, source_path) "
            "SELECT id, text, heading, source_path FROM kb_chunk"
        )
    return count


def rebuild() -> dict[str, int]:
    db.init()
    with db.session() as conn:
        conn.execute("DELETE FROM kg_edge")
        conn.execute("DELETE FROM kg_node")
        graph = Graph(conn)
        ingest_people(graph)
        ingest_departments(graph)
        ingest_systems(graph)
        ingest_datasets(graph)
        ingest_strategy(graph)
        ingest_projects(graph)
        ingest_policies_and_processes(graph)
        ingest_decisions(graph)
        chunks = ingest_chunks(conn)

        types = dict(conn.execute(
            "SELECT type, COUNT(*) FROM kg_node GROUP BY type ORDER BY 2 DESC"
        ).fetchall())
        rels = dict(conn.execute(
            "SELECT rel, COUNT(*) FROM kg_edge GROUP BY rel ORDER BY 2 DESC"
        ).fetchall())
        node_total = conn.execute("SELECT COUNT(*) FROM kg_node").fetchone()[0]
        edge_total = conn.execute("SELECT COUNT(*) FROM kg_edge").fetchone()[0]
        db.log(conn, "system", "kg.rebuild", detail={"nodes": node_total,
                                                     "edges": edge_total,
                                                     "chunks": chunks})
    return {"nodes": node_total, "edges": edge_total, "chunks": chunks,
            "by_type": types, "by_rel": rels}


if __name__ == "__main__":
    stats = rebuild()
    print(f"nodes  {stats['nodes']}")
    for node_type, count in stats["by_type"].items():
        print(f"  {node_type:<18} {count:>4}")
    print(f"edges  {stats['edges']}")
    for rel, count in stats["by_rel"].items():
        print(f"  {rel:<18} {count:>4}")
    print(f"chunks {stats['chunks']}")
