"""The portal: one login, and a page that depends on who logged in.

    .venv/bin/python portal/app.py

The innovation user gets the Innovation Dashboard, employees get the Employee
Interface.
"""

import subprocess
from pathlib import Path

import gradio as gr

import employee_interface
import innovation_dashboard
from auth import check_login, find_employee, is_dashboard_user
from db import connect, create_tables
from score_ideas import load_setups
from theme import CSS, THEME, login_message


def latest_commit_time() -> str:
    """When the checked-out code was committed, or "unknown" without git."""
    try:
        return subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M %z"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def show_page(request: gr.Request):
    """The signed-in label, and which of the two pages is visible."""
    username = request.username or ""
    dashboard = is_dashboard_user(username)
    if dashboard:
        label = "**Innovation team**  ·  all submitted ideas"
    elif employee := find_employee(username):
        label = (f"**{employee['name']}**  ·  {employee['id']}"
                 f"  ·  {employee.get('department', '')}".rstrip(" ·"))
    else:
        label = "**Unknown user**  ·  your login matches no employee"
    return label, gr.update(visible=not dashboard), gr.update(visible=dashboard)


with gr.Blocks(title="Idea Portal", fill_height=True) as demo:
    with gr.Row(elem_id="portal-bar", equal_height=True):
        gr.Markdown("# Idea Portal\nBrambleworks GmbH",
                    elem_id="portal-brand", scale=3)
        user_label = gr.Markdown(elem_id="portal-who", scale=4)
        gr.Button("Log out", link="/logout?all_session=false", size="sm",
                  scale=0, min_width=100)
    # Hiding a page is not access control: each page also checks the user itself.
    with gr.Column(visible=False, scale=1) as employee_page:
        employee_interface.build()
    with gr.Column(visible=False) as dashboard_page:
        innovation_dashboard.build(demo)
    demo.load(show_page, outputs=[user_label, employee_page, dashboard_page])


def check_database() -> None:
    """Fail at startup, not at the first login, if the database is not ready."""
    with connect() as connection:
        create_tables(connection)
        if not connection.execute("SELECT 1 FROM knowledge_base.employees LIMIT 1").fetchone():
            raise SystemExit("No employees in the database. Run sync_knowledge_base.py.")


if __name__ == "__main__":
    check_database()
    load_setups()  # Fail at startup if a metric or the checks file is broken.
    # The login page is rendered separately and never sees `css`, so its styles
    # travel inside auth_message. See theme.login_message().
    demo.launch(
        auth=check_login,
        theme=THEME,
        css=CSS,
        auth_message=login_message(latest_commit_time()),
    )
