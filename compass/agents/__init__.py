"""The evaluation agents.

Each module exposes `assess(record, conn) -> (payload, model)` and keeps its
offline rules beside its prompt, so the two can be compared and kept honest
against each other.
"""
