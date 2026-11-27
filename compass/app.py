"""AI Compass: the dashboard.

Two audiences in one app, separated by the access role on the login:

  every employee   Ask the company, My ideas
  decision board   + Portfolio, Scoring method, Review queue

Tabs are hidden for roles that may not use them, but that is only tidiness.
Every handler re-checks the role through compass.views, so calling an endpoint
directly gets you an access error rather than data.

Run:  python -m compass.app      (http://127.0.0.1:7861)

The employee intake chat is a separate app, employee_interface/app.py, which
writes submissions to knowledge-base/ideas/raw/.
"""

from __future__ import annotations

import os

import gradio as gr

from . import config, db, llm, views
from .agents import orchestrator

PORT = 7861

# Set by compass/serve.py, which mounts this app and the intake chat on one
# port. Standalone on :7861 there is no /intake route, so the link is hidden
# rather than offered and broken.
COMBINED = os.environ.get("COMPASS_COMBINED") == "1"

# "false" ends only this browser session; "true" would also sign the same
# employee out of every other tab and device. False is deliberate: switching
# between an admin and an employee view in two tabs is the fastest way to show
# that the access rules are real.
LOGOUT_ALL_SESSIONS = "false"

# Upper bound for the cost filter when there is nothing to size it from.
COST_FILTER_MAX = 25_000

CSS = """
.compass-table table { font-size: 12px; }
.compass-detail { max-height: 72vh; overflow-y: auto; }
footer { display: none !important; }
"""


def _viewer(request: gr.Request) -> views.Viewer:
    return views.viewer_for(getattr(request, "username", "") or "")


def _rows(viewer: views.Viewer) -> list[dict]:
    with db.session() as conn:
        return views.portfolio(conn, viewer)


# --------------------------------------------------------------------------- #
# handlers
# --------------------------------------------------------------------------- #
def on_load(request: gr.Request):
    viewer = _viewer(request)
    header = (f"**{viewer.name}** ({viewer.employee_id}, "
              f"{viewer.department or 'unknown team'}) — access role "
              f"`{viewer.role}`  \n{llm.banner()}")

    board = gr.update(visible=viewer.is_admin)
    review = gr.update(visible=viewer.may_review)

    if viewer.is_admin:
        with db.session() as conn:
            rows = views.portfolio(conn, viewer)
            summary = views.portfolio_summary(conn, rows)
            departments = sorted({r["department"] for r in rows})
            costs = [r["est_cost_eur"] for r in rows]
        table = views.to_table(rows)
    else:
        summary, table, departments, costs = "", [], [], []

    # The slider's minimum is 0, so a maximum of 0 makes Gradio refuse to
    # rebuild the component and the whole page load fails. That is reachable
    # with no costed ideas and for every non-admin, who gets no rows at all.
    cost_ceiling = max(costs) if costs and max(costs) > 0 else COST_FILTER_MAX

    with db.session() as conn:
        mine = views.my_ideas(conn, viewer)
        queue = (views.review_queue(conn, viewer) if viewer.may_review else [])
        active = db.get_active_scoring(conn)

    return (header, board, board, review, summary, table,
            gr.update(choices=departments, value=[]),
            gr.update(maximum=cost_ceiling, value=cost_ceiling),
            mine, queue,
            gr.update(choices=config.available_scoring_configs(), value=active),
            f"Active scoring config: **{active}**")


def apply_filters(max_cost, max_people, max_days, departments, ai_fits,
                  feasibilities, risk_clear, hide_unscored, needs_review,
                  request: gr.Request):
    viewer = _viewer(request)
    try:
        with db.session() as conn:
            rows = views.portfolio(conn, viewer)
            filtered = views.filter_portfolio(
                rows, max_cost=int(max_cost), max_people=int(max_people),
                max_person_days=int(max_days),
                departments=departments or None, ai_fits=ai_fits or None,
                feasibilities=feasibilities or None,
                risk_clear_only=bool(risk_clear),
                hide_unscored=bool(hide_unscored),
                needs_review_only=bool(needs_review))
            summary = views.portfolio_summary(conn, filtered)
    except views.AccessDenied as error:
        return [], f"**Access denied.** {error}"
    note = ""
    if len(filtered) != len(rows):
        note = f"  \nShowing {len(filtered)} of {len(rows)} ideas."
    return views.to_table(filtered), summary + note


def show_detail(table, event: gr.SelectData, request: gr.Request):
    viewer = _viewer(request)
    try:
        row_index = event.index[0] if isinstance(event.index, (list, tuple)) \
            else event.index
        use_case_id = table.iloc[row_index, 1] if hasattr(table, "iloc") \
            else table[row_index][1]
    except Exception:
        return "Select a row to see the full assessment.", ""
    try:
        with db.session() as conn:
            return views.detail(conn, viewer, str(use_case_id)), str(use_case_id)
    except views.AccessDenied as error:
        return f"**Access denied.** {error}", ""


def decide(use_case_id: str, decision: str, note: str, request: gr.Request):
    viewer = _viewer(request)
    if not use_case_id:
        return "Select an idea first.", gr.skip()
    try:
        with db.session() as conn:
            message = views.record_decision(conn, viewer, use_case_id,
                                            decision, note)
            rows = views.portfolio(conn, viewer)
        return message, views.to_table(rows)
    except views.AccessDenied as error:
        return f"**Access denied.** {error}", gr.skip()


def switch_scoring(name: str, request: gr.Request):
    """Re-rank the whole portfolio under a different config and explain it."""
    viewer = _viewer(request)
    try:
        views.require_admin(viewer)
    except views.AccessDenied as error:
        return f"**Access denied.** {error}", [], gr.skip()

    with db.session() as conn:
        difference = orchestrator.rescore_all(conn, name)
        rows = views.portfolio(conn, viewer)
        spec = config.scoring_config(name)

    lines = [f"### Re-ranked under {spec.get('label', name)}",
             f"`{name}` · formula `{spec.get('formula')}` · "
             f"{difference['total']} ideas scored, "
             f"{len(difference['moved'])} changed position or score, "
             f"{difference['unchanged']} unchanged.", ""]
    if difference["moved"]:
        lines += ["| Idea | Was | Now | Moved | Why |", "|---|---|---|---|---|"]
        for move in difference["moved"][:25]:
            lines.append(
                f"| {move['use_case_id']} {move['title'][:34]} | "
                f"{move['rank_before']} | {move['rank_after']} | "
                f"{move['direction']} {move['places_moved']} | "
                f"{'; '.join(move['factor_changes']) or 'score recomputed'} "
                f"({move['score_before']} → {move['score_after']}) |")
    else:
        lines.append("Nothing moved: the two configs rank this portfolio "
                     "identically.")
    lines += ["", "*Risk flags and feasibility are properties of the idea and "
              "are not re-computed here. Only the business score changes.*"]
    return "\n".join(lines), views.to_table(rows), \
        f"Active scoring config: **{name}**"


def ask(question: str, history: list, request: gr.Request):
    viewer = _viewer(request)
    with db.session() as conn:
        answer = views.ask_knowledge_base(conn, viewer, question)
    return answer


def select_idea(use_case_id: str, note: str, request: gr.Request):
    return decide(use_case_id, "selected", note, request)


def park_idea(use_case_id: str, note: str, request: gr.Request):
    return decide(use_case_id, "parked", note, request)


def reject_idea(use_case_id: str, note: str, request: gr.Request):
    return decide(use_case_id, "rejected", note, request)


def refresh_queue(mine_only: bool, request: gr.Request):
    viewer = _viewer(request)
    try:
        with db.session() as conn:
            return views.review_queue(conn, viewer, mine_only=bool(mine_only))
    except views.AccessDenied as error:
        gr.Warning(str(error))
        return []


# --------------------------------------------------------------------------- #
# interface
# --------------------------------------------------------------------------- #
with gr.Blocks(title="AI Compass", fill_height=True) as demo:
    gr.Markdown("# AI Compass\nFrom employee ideas to a ranked, screened "
                "portfolio. **The agent recommends; people decide.**")
    with gr.Row(equal_height=True):
        who = gr.Markdown()
        # Gradio's own /logout route clears the auth cookies and redirects to
        # the login screen. all_session=false logs out only this browser
        # session, so a second tab signed in as another employee stays open -
        # which is how you compare what an admin and an employee can see.
        # Same pattern and parameter as employee_interface/app.py, so logging
        # out behaves identically in both apps.
        if COMBINED:
            gr.Button("Submit an idea", link="/intake/", size="sm", scale=0,
                      min_width=140)
        gr.Button("Log out", link=f"/logout?all_session={LOGOUT_ALL_SESSIONS}",
                  size="sm", scale=0, min_width=110)
    selected_id = gr.State("")

    with gr.Tab("Ask the company"):
        gr.Markdown("Ask about processes, policies, products or who to ask. "
                    "Answers come from the knowledge base and cite the page "
                    "they came from. You only see what your access role allows.")
        gr.ChatInterface(
            fn=ask,
            textbox=gr.Textbox(
                placeholder="How much learning budget do I get? Which systems "
                            "have no API?", submit_btn=True),
            examples=["How many days of vacation do I get?",
                      "Who approves a EUR 8,000 purchase?",
                      "Which systems have no API?",
                      "What does our AI usage policy forbid?",
                      "Who do I ask about a data protection request?"],
        )

    with gr.Tab("My ideas"):
        gr.Markdown("Your own submissions. Submit a new idea in the intake "
                    "chat (`employee_interface/app.py`). Assessment results "
                    "are shown to the decision board, not here — but anything "
                    "**waiting on you** appears in the last column.")
        mine_table = gr.Dataframe(headers=views.MINE_HEADERS, interactive=False,
                                  wrap=True, elem_classes="compass-table")

    with gr.Tab("Portfolio", visible=False) as portfolio_tab:
        summary_line = gr.Markdown()
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("#### Filters")
                cost_filter = gr.Slider(0, COST_FILTER_MAX, step=500,
                                        value=COST_FILTER_MAX,
                                        label="Max cost (EUR)")
                people_filter = gr.Slider(1, 8, value=8, step=1,
                                          label="Max people required")
                days_filter = gr.Slider(1, 120, value=120, step=5,
                                        label="Max person-days")
                department_filter = gr.Dropdown([], multiselect=True,
                                                label="Department")
                ai_fit_filter = gr.Dropdown(
                    ["ai", "conventional_automation", "hybrid",
                     "more_research"], multiselect=True, label="AI fit")
                feasibility_filter = gr.Dropdown(
                    ["doable", "doable_with_constraints", "not_doable_now",
                     "unknown"], multiselect=True, label="Feasibility")
                risk_clear = gr.Checkbox(
                    label="Only ideas no risk gate blocks")
                hide_unscored = gr.Checkbox(label="Hide unscored ideas")
                needs_review = gr.Checkbox(
                    label="Only ideas with open review items")
                gr.Markdown("*Business score and risk flags are separate "
                            "columns. A high score never clears a gate.*")
            with gr.Column(scale=4):
                table = gr.Dataframe(headers=views.TABLE_HEADERS,
                                     interactive=False, wrap=True,
                                     elem_classes="compass-table")
                gr.Markdown("Select a row to see the full assessment.")
                with gr.Row():
                    decision_note = gr.Textbox(
                        label="Note for the decision log", scale=3)
                    select_button = gr.Button("Select", variant="primary",
                                              scale=1)
                    park_button = gr.Button("Park", scale=1)
                    reject_button = gr.Button("Reject", scale=1)
                decision_message = gr.Markdown()
        detail_panel = gr.Markdown("Select a row to see the full assessment.",
                                   elem_classes="compass-detail")

    with gr.Tab("Scoring method", visible=False) as scoring_tab:
        gr.Markdown(
            "The scoring method is a config file, not code. Switching it "
            "re-ranks the portfolio and shows exactly what moved and why.\n\n"
            "- `rice-v1` — balanced RICE\n"
            "- `rice-v2-cost-weighted` — prices the effort and penalises "
            "scarce skills, for when budget is the binding constraint")
        active_line = gr.Markdown()
        with gr.Row():
            scoring_choice = gr.Dropdown([], label="Scoring config", scale=3)
            apply_scoring = gr.Button("Apply and re-rank", variant="primary",
                                      scale=1)
        diff_panel = gr.Markdown()

    with gr.Tab("Review queue", visible=False) as review_tab:
        gr.Markdown("Gaps and uncertainties the agent raised for a person to "
                    "resolve. Nothing here was guessed: these are the "
                    "questions it refused to answer on its own.")
        mine_only = gr.Checkbox(label="Only items assigned to me")
        queue_table = gr.Dataframe(headers=views.REVIEW_HEADERS,
                                   interactive=False, wrap=True,
                                   elem_classes="compass-table")

    # --- wiring -----------------------------------------------------------
    demo.load(
        on_load,
        outputs=[who, portfolio_tab, scoring_tab, review_tab, summary_line,
                 table, department_filter, cost_filter, mine_table,
                 queue_table, scoring_choice, active_line],
    )

    filter_inputs = [cost_filter, people_filter, days_filter,
                     department_filter, ai_fit_filter, feasibility_filter,
                     risk_clear, hide_unscored, needs_review]
    for control in filter_inputs:
        control.change(apply_filters, inputs=filter_inputs,
                       outputs=[table, summary_line])

    table.select(show_detail, inputs=[table],
                 outputs=[detail_panel, selected_id])

    select_button.click(select_idea, inputs=[selected_id, decision_note],
                        outputs=[decision_message, table])
    park_button.click(park_idea, inputs=[selected_id, decision_note],
                      outputs=[decision_message, table])
    reject_button.click(reject_idea, inputs=[selected_id, decision_note],
                        outputs=[decision_message, table])

    apply_scoring.click(switch_scoring, inputs=[scoring_choice],
                        outputs=[diff_panel, table, active_line])

    mine_only.change(refresh_queue, inputs=[mine_only], outputs=[queue_table])


if __name__ == "__main__":
    if not views.LOGINS.exists():
        raise SystemExit(
            "No demo logins found. Run: python seed/generate_logins.py")
    with db.session() as connection:
        if not connection.execute(
            "SELECT COUNT(*) FROM use_cases").fetchone()[0]:
            raise SystemExit(
                "No assessed ideas found. Run: python -m seed.load")
    demo.launch(auth=views.check_login, server_port=PORT, css=CSS,
                auth_message="Log in with your employee ID.")
