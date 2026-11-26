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
        label = "Signed in as **Innovation team**"
    elif employee := find_employee(username):
        label = f"Signed in as **{employee['name']}** ({employee['id']})"
    else:
        label = "Signed in as **unknown**"
    return label, gr.update(visible=not dashboard), gr.update(visible=dashboard)


with gr.Blocks(title="Idea Portal", fill_height=True) as demo:
    with gr.Row(equal_height=True):
        user_label = gr.Markdown()
        gr.Button("Log out", link="/logout?all_session=false", size="sm", scale=0)
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
    # The login page only takes a message, so CSS moves the commit time to the bottom.
    footer = (
        '<span style="position: fixed; bottom: 1rem; left: 0; right: 0; '
        f'text-align: center; font-size: small">Latest commit: {latest_commit_time()}</span>'
    )
    demo.launch(
        auth=check_login,
        auth_message=f"Employees: log in with your last name in lowercase.{footer}",
    )
