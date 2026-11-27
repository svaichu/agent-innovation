"""The dashboard listing as HTML: stat tiles, and one table row per idea.

Idea, model and employee texts end up in raw HTML here, so every one of them goes
through esc().
"""

import html
from dataclasses import dataclass, field, replace

from idea_store import RawIdea
from refined_store import RefinedIdea
from score_store import Score

# AI Act tiers, mildest first. A tier not listed here is the Art. 6(3) exception.
SEVERITY = {"minimal": 0, "needs_review": 2, "high-risk": 3, "prohibited": 4}
ACT_TONES = {0: "green", 1: "amber", 2: "amber", 3: "red", 4: "red"}
FITS = {
    "AI": ("AI", "blue"),
    "conventional automation": ("Automation", "grey"),
    "more research": ("More research", "amber"),
}


@dataclass(frozen=True)
class Column:
    """One metric, shown as a column of scores."""

    name: str
    label: str


@dataclass
class Row:
    """What one line of the table shows."""

    idea: RawIdea | RefinedIdea
    department: str
    # Plain text under the title.
    byline: str
    # The ideas a refined idea was merged from, with their authors and whether
    # each changed since. Empty for a raw idea.
    sources: list[tuple[str, str, str, bool]]
    # By metric name.
    scores: dict[str, Score] = field(default_factory=dict)


def esc(value: object) -> str:
    """Text that can only ever be read as text, also by the page's templates."""
    text = html.escape(" ".join(str(value).split()))
    return text.replace("$", "&#36;").replace("{", "&#123;")


def idea_title(idea: RawIdea | RefinedIdea) -> str:
    """The first line of the idea, without its leading '# '."""
    first_line, _, _ = idea.text.partition("\n")
    return first_line.removeprefix("# ").strip() or idea.id


def author_line(idea: RawIdea) -> str:
    if not idea.author_name:
        return f"{idea.author_id} · not in the employee list"
    return f"{idea.author_name} · {idea.author_id}"


def day(moment) -> str:
    return f"{moment.astimezone():%d %b %Y}"


def raw_row(idea: RawIdea) -> Row:
    byline = f"{author_line(idea)} · {day(idea.created_at)}"
    if idea.version > 1 and idea.updated_at:
        byline += f" · v{idea.version}, updated {day(idea.updated_at)}"
    return Row(idea, idea.department or "", byline, [])


def refined_row(item: RefinedIdea, ideas: dict[str, RawIdea]) -> Row:
    sources, departments = [], []
    for idea_id, version in sorted(item.sources.items()):
        if idea := ideas.get(idea_id):
            sources.append(
                (idea_id, idea_title(idea), author_line(idea), idea.version != version)
            )
            if idea.department and idea.department not in departments:
                departments.append(idea.department)
        else:
            sources.append((idea_id, "", "", False))
    byline = f"Merged from {', '.join(sorted(item.sources))}"
    if item.saved_at:
        byline += f" · {day(item.saved_at)}"
    if item.version > 1:
        byline += f" · v{item.version}"
    return Row(item, ", ".join(sorted(departments)), byline, sources)


# --------------------------------------------------------------------------- #
# cells
# --------------------------------------------------------------------------- #
def pill(text: str, tone: str = "grey", hint: str = "") -> str:
    title = f' title="{esc(hint)}"' if hint else ""
    return f'<span class="pill {tone}"{title}>{esc(text)}</span>'


def severity(act: dict) -> int:
    return SEVERITY.get(act["tier"], 1)


def checks_of(scores: dict[str, Score], columns: list[Column]) -> dict | None:
    """The flags of an idea, across the runs of all its metrics.

    Every run answers the checks again, and the answers can differ. AI fit is
    taken from the first metric; for the AI Act the strictest answer counts.
    """
    found = [scores[c.name].details for c in columns if c.name in scores]
    if not found:
        return None
    act = max((d["ai_act"] for d in found), key=severity)
    return {
        "ai_fit": found[0]["ai_fit"],
        "ai_act": act,
        "transparency": sorted({t for d in found for t in d["ai_act"]["transparency"]}),
        "review_required": any(d["review_required"] for d in found),
    }


def act_pill(checks: dict) -> str:
    act = checks["ai_act"]
    tier, level = act["tier"], severity(act)
    hint = "; ".join([*act["citations"], *checks["transparency"]])
    if level == 0 and checks["transparency"]:
        article = checks["transparency"][0].split("(")[0].strip()
        return pill(f"transparency · {article}", "amber", hint)
    if level == 1:
        return pill("exception · Art. 6(3)", "amber", hint or tier)
    return pill(tier.replace("_", " "), ACT_TONES[level], hint)


def status_of(row: Row, columns: list[Column]) -> tuple[str, str]:
    """What the idea is waiting for, and its colour. The first match wins."""
    scores = row.scores
    checks = checks_of(scores, columns)
    if checks is None:
        return "Score pending", "grey"
    if checks["review_required"]:
        return "Needs review", "red"
    if any(changed for *_, changed in row.sources):
        return "Source changed", "amber"
    if any(c.name not in scores for c in columns):
        return "Partly scored", "grey"
    if any(scores[c.name].value is None for c in columns):
        return "Needs info", "amber"
    return "Scored", "green"


def score_cell(score: Score | None) -> str:
    if score is None:
        return '<span class="muted">pending</span>'
    if score.value is None:
        return '<span class="muted">— needs info</span>'
    estimated = len(score.details["estimated"])
    note = f"<small>{estimated} estimated</small>" if estimated else ""
    return (
        f'<span class="meter"><i style="width:{int(score.value)}%"></i></span>'
        f"<b>{int(score.value)}</b>{note}"
    )


# --------------------------------------------------------------------------- #
# the opened row
# --------------------------------------------------------------------------- #
def idea_html(text: str) -> str:
    """The idea's own sections. Everything but its headings stays plain text."""
    _, _, body = text.partition("\n")
    parts: list[str] = []
    lines: list[str] = []

    def flush() -> None:
        if lines:
            parts.append(f"<p>{'<br>'.join(esc(line) for line in lines)}</p>")
            lines.clear()

    for line in body.splitlines():
        if line.startswith("#"):
            flush()
            parts.append(f"<h5>{esc(line.lstrip('#'))}</h5>")
        elif line.strip():
            lines.append(line)
        else:
            flush()
    flush()
    return "".join(parts)


def bullets(items: list[str]) -> str:
    return f"<ul>{''.join(f'<li>{item}</li>' for item in items)}</ul>" if items else ""


def section(title: str, body: str, opened: bool) -> str:
    """A part of the reasons that opens and closes. The title is already escaped."""
    state = " open" if opened else ""
    return f'<details class="metric"{state}><summary>{title}</summary>{body}</details>'


def metric_html(column: Column, score: Score | None, opened: bool) -> str:
    """Why the idea got this score under one metric."""
    if score is None:
        return section(
            esc(column.label), '<p class="muted">Not scored yet.</p>', opened
        )
    details = score.details
    value = "needs information" if score.value is None else f"{score.value}/100"
    items = []
    for name, item in details["inputs"].items():
        if item["value"] is None:
            continue
        source = item["source"].replace("_", " ")
        line = (
            f"<b>{esc(name.replace('_', ' '))}</b> {item['value']:g} "
            f"<em>({esc(source)})</em> {esc(item['evidence'])}"
        )
        if item["source"] == "estimate":
            line += bullets([f"based on: {esc(fact)}" for fact in item["basis"]])
        items.append(line)
    items += [f"<b>Warning:</b> {esc(flag)}" for flag in details["flags"]]
    items += [f"<b>Open:</b> {esc(question)}" for question in details["open_questions"]]
    return section(
        f"{esc(column.label)} · {value}",
        f'<p class="muted">{esc(score.rationale)}</p>{bullets(items)}',
        opened,
    )


def flags_html(checks: dict) -> str:
    fit, act = checks["ai_fit"], checks["ai_act"]
    items = [f"AI fit, rule {int(fit['rule'])}: {esc(fit['reason'])}"]
    if act["citations"]:
        applies = f" ({act['applies']})" if act["applies"] else ""
        items.append(f"AI Act: {esc('; '.join(act['citations']) + applies)}")
    items += [f"Transparency duty: {esc(duty)}" for duty in checks["transparency"]]
    items += [f"To check: {esc(problem)}" for problem in act["problems"]]
    return section(
        "Flags",
        f'{bullets(items)}<p class="muted">Preliminary screening, not legal advice.</p>',
        checks["review_required"],
    )


def detail_html(row: Row, columns: list[Column], sorted_by: str) -> str:
    left = idea_html(row.idea.text)
    if row.sources:
        items = []
        for idea_id, title, author, changed in row.sources:
            line = f"<b>{esc(idea_id)}</b> {esc(title)}"
            if author:
                line += f' <span class="muted">— {esc(author)}</span>'
            if changed:
                line += " " + pill("Changed since merge", "amber")
            items.append(line)
        why = f"<h5>Why merged</h5><p>{esc(row.idea.rationale)}</p>"
        if row.idea.differences:
            why += "<h5>To settle</h5>"
            why += bullets([esc(d) for d in row.idea.differences])
        left = f"<h5>Merged from</h5>{bullets(items)}{why}<hr>{left}"
    # The metric the list is ranked by starts open, otherwise the first one.
    names = [c.name for c in columns]
    focus = sorted_by if sorted_by in names else names[0]
    right = "".join(
        metric_html(c, row.scores.get(c.name), c.name == focus) for c in columns
    )
    if checks := checks_of(row.scores, columns):
        right += flags_html(checks)
    return f'<div class="detail"><div>{left}</div><div>{right}</div></div>'


# --------------------------------------------------------------------------- #
# table and tiles
# --------------------------------------------------------------------------- #
def row_html(row: Row, columns: list[Column], sorted_by: str, opened: bool) -> str:
    checks = checks_of(row.scores, columns)
    dash = '<span class="muted">—</span>'
    fit, act, questions = dash, dash, dash
    if checks:
        fit = pill(*FITS.get(checks["ai_fit"]["label"], (checks["ai_fit"]["label"],)))
        act = act_pill(checks)
        # Of the first scored metric: the others tend to ask the same in other words.
        first = next(row.scores[c.name] for c in columns if c.name in row.scores)
        questions = str(len(first.details["open_questions"]))
    scores = "".join(
        f'<span class="score" data-label="{esc(c.label)}">'
        f"{score_cell(row.scores.get(c.name))}</span>"
        for c in columns
    )
    return (
        f'<details class="idea"{" open" if opened else ""}><summary class="line">'
        f'<span class="id">{esc(row.idea.id)}</span>'
        f'<span class="title"><b>{esc(idea_title(row.idea))}</b>'
        f"<small>{esc(row.byline)}</small></span>"
        f"<span>{esc(row.department.title()) or dash}</span>{scores}"
        f"<span>{fit}</span><span>{act}</span>"
        f"<span>{pill(*status_of(row, columns))}</span>"
        f"<span>{questions}</span>"
        f"</summary>{detail_html(row, columns, sorted_by)}</details>"
    )


def table_html(
    rows: list[Row],
    scores: dict[str, dict[str, Score]],
    columns: list[Column],
    sorted_by: str = "",
) -> str:
    """The ideas in the given order.

    Args:
        scores: By idea ID, then by metric name.
        sorted_by: The name of the metric the rows are ranked by, if any.
    """
    heads = "".join(
        f'<span class="{"sorted" if c.name == sorted_by else ""}">{esc(c.label)}'
        f"{' ▼' if c.name == sorted_by else ''}<small>0–100</small></span>"
        for c in columns
    )
    rows = [replace(row, scores=scores.get(row.idea.id, {})) for row in rows]
    body = "".join(
        row_html(row, columns, sorted_by, len(rows) == 1) for row in rows
    )
    return (
        f'<div class="ideas" style="--metrics:{len(columns)}"><div class="grid">'
        '<div class="line head"><span>ID</span><span>Idea</span><span>Dept.</span>'
        f"{heads}<span>AI fit</span><span>EU AI Act</span><span>Status</span>"
        '<span title="Open questions">Open q.</span></div>'
        f"{body}</div></div>"
        '<p class="ideas-note">Select a row to read the idea and the reasons. '
        "Each score column uses one metric. The flags are shown next to the scores "
        "and never mixed into them.</p>"
    )


def tiles_html(
    ideas: list[RawIdea],
    refined: list[RefinedIdea],
    scores: dict[str, dict[str, Score]],
    columns: list[Column],
) -> str:
    """Counts over raw and refined ideas together, unless the caption says else."""
    own = [scores.get(item.id, {}) for item in [*ideas, *refined]]
    pending = sum(any(c.name not in s for c in columns) for s in own)
    needs_info = sum(any(score.value is None for score in s.values()) for s in own)
    review = sum(
        bool((checks := checks_of(s, columns)) and checks["review_required"])
        for s in own
    )
    tiles = [
        (len(ideas), "submitted ideas", ""),
        (len(refined), "refined ideas", "purple"),
        (len({i.author_id for i in ideas}), "contributors", "blue"),
        (pending, "awaiting a score", "grey"),
        (needs_info, "need information", "amber"),
        (review, "need review (AI Act)", "red"),
    ]
    return '<div class="tiles">' + "".join(
        f'<div class="tile {tone}"><b>{number}</b><span>{caption}</span></div>'
        for number, caption, tone in tiles
    ) + "</div>"
