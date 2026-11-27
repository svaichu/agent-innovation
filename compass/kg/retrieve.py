"""Text retrieval over the knowledge base, filtered by classification.

Used by the knowledge chatbot and to give agents narrative context.

Ranking is a TF-IDF scorer in pure Python, because it can weigh two signals
SQLite's FTS5 cannot reach: a match in the section heading, and a match in the
filename. In a hand-written knowledge base both are deliberate statements of
what a page is about. `_search_fts` remains available for raw matching, and the
corpus is small enough (around 160 chunks) that scoring it in Python is free.

No API key is needed, which is why the knowledge chatbot still answers when no
model is configured.

Classification is enforced here rather than in the UI. An employee asking about
strategy gets "that is confidential", not a leaked paragraph.
"""

from __future__ import annotations

import math
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass

from .. import config, db

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "by",
    "from", "our", "we", "it", "is", "are", "be", "that", "this", "their",
    "what", "who", "how", "when", "where", "which", "do", "does", "can", "i",
    "my", "you", "your", "me", "at", "as", "if", "not", "no", "but", "there",
}


@dataclass
class Chunk:
    source_path: str
    heading: str
    text: str
    classification: str
    score: float

    def citation(self) -> str:
        return f"{self.source_path}" + (f" ({self.heading})" if self.heading else "")


def terms(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in STOPWORDS]


def _allowed_classifications(role: str) -> list[str]:
    limit = config.CLASSIFICATION_ORDER.index(config.max_classification_for(role))
    return config.CLASSIFICATION_ORDER[: limit + 1]


def search(conn: sqlite3.Connection, query: str, role: str = "employee",
           limit: int = 5) -> list[Chunk]:
    allowed = _allowed_classifications(role)
    # The TF-IDF scorer weighs heading and filename matches, which FTS5 cannot
    # (source_path is UNINDEXED there), and this corpus is small enough that
    # scoring it in Python costs nothing. FTS stays available for callers that
    # want raw matching.
    return _search_tfidf(conn, query, allowed, limit)


def _search_fts(conn: sqlite3.Connection, query: str, allowed: list[str],
                limit: int) -> list[Chunk]:
    words = terms(query)
    if not words:
        return []
    # OR rather than AND: a question rarely shares every word with the answer.
    expression = " OR ".join(f'"{w}"' for w in words)
    placeholders = ",".join("?" for _ in allowed)
    try:
        rows = conn.execute(
            f"""
            SELECT c.source_path, c.heading, c.text, c.classification,
                   bm25(kb_chunk_fts) AS rank
            FROM kb_chunk_fts f
            JOIN kb_chunk c ON c.id = f.rowid
            WHERE kb_chunk_fts MATCH ?
              AND c.classification IN ({placeholders})
            ORDER BY rank LIMIT ?
            """,
            (expression, *allowed, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    # bm25 returns lower-is-better; flip it so higher is better everywhere.
    return [Chunk(r["source_path"], r["heading"], r["text"],
                  r["classification"], -float(r["rank"])) for r in rows]


def _search_tfidf(conn: sqlite3.Connection, query: str, allowed: list[str],
                  limit: int) -> list[Chunk]:
    placeholders = ",".join("?" for _ in allowed)
    rows = conn.execute(
        f"SELECT source_path, heading, text, classification FROM kb_chunk "
        f"WHERE classification IN ({placeholders})",
        tuple(allowed),
    ).fetchall()
    if not rows:
        return []

    documents = [terms(f"{r['heading']} {r['text']}") for r in rows]
    frequencies = Counter()
    for document in documents:
        frequencies.update(set(document))
    total = len(documents)

    wanted = terms(query)
    scored: list[tuple[float, sqlite3.Row]] = []
    for row, document in zip(rows, documents):
        if not document:
            continue
        counts = Counter(document)
        score = 0.0
        for word in wanted:
            if word not in counts:
                continue
            tf = counts[word] / len(document)
            idf = math.log(1 + total / (1 + frequencies[word]))
            score += tf * idf
        # A heading match is a strong signal that the section is on topic.
        if wanted and any(w in terms(row["heading"]) for w in wanted):
            score *= 1.5
        # So is the filename. In a hand-written knowledge base the path is
        # chosen to say what the page is about: "ai-usage.md" answers "what
        # does the AI usage policy forbid?" even though the body never uses
        # the word "forbid".
        path_terms = terms(row["source_path"].replace("/", " ").replace("-", " "))
        matched_path = sum(1 for w in set(wanted) if w in path_terms)
        if matched_path:
            score *= 1.0 + 0.6 * matched_path
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda item: -item[0])
    return [Chunk(r["source_path"], r["heading"], r["text"],
                  r["classification"], s) for s, r in scored[:limit]]


def context_block(chunks: list[Chunk], max_chars: int = 4000) -> str:
    """Retrieved chunks formatted for a prompt, each with its citation."""
    parts: list[str] = []
    used = 0
    for chunk in chunks:
        body = chunk.text.strip()
        entry = f"[{chunk.citation()}]\n{body}"
        if used + len(entry) > max_chars:
            break
        parts.append(entry)
        used += len(entry)
    return "\n\n".join(parts)


def restricted_hits(conn: sqlite3.Connection, query: str, role: str) -> int:
    """How many matching chunks the role may NOT see.

    Lets the chatbot say "there is material on this that your role cannot
    access, ask E26" instead of pretending nothing exists.
    """
    everything = _search_tfidf(conn, query, config.CLASSIFICATION_ORDER, 50)
    allowed = set(_allowed_classifications(role))
    return sum(1 for chunk in everything if chunk.classification not in allowed)


if __name__ == "__main__":
    with db.session() as connection:
        for role in ("employee", "admin"):
            print(f"=== role: {role} ===")
            for question in ("How many days of vacation do I get?",
                             "What is our ARR target for 2027?",
                             "Which systems have no API?"):
                hits = search(connection, question, role=role, limit=2)
                print(f"\nQ: {question}")
                for hit in hits:
                    first = hit.text.strip().splitlines()[0][:90]
                    print(f"  {hit.score:6.3f}  {hit.citation()}")
                    print(f"          {first}")
                blocked = restricted_hits(connection, question, role)
                if blocked:
                    print(f"  ({blocked} matching sections hidden by classification)")
            print()
