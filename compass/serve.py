"""Serve both apps from one port, behind one login.

    python -m compass.serve            ->  http://127.0.0.1:7860

        /          the board  (compass/app.py)
        /intake    the idea chat  (employee_interface/app.py)

Why this file exists
--------------------
The two apps grew separately and ended up on two ports with two separate login
systems, so a demo meant signing in twice and could leave you logged in as two
different people in two tabs. Gradio can mount several Blocks onto one FastAPI
server, so both are reachable at one address with one set of credentials.

Nothing in employee_interface/ is modified. Its `demo` object is imported and
mounted as it is; its own `demo.launch()` stays guarded behind `__main__`, so
importing it does not start a second server. That app can still be run on its
own exactly as before.

The shared login is compass.views.check_login, which reads
seed/data/demo_logins.csv — all 120 employees, with access roles. The five
logins in employee_interface/users.csv are reused verbatim in that file, so
every credential that worked before still works here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("COMPASS_PORT", 7860))

# Tell compass.app it is running behind the combined server, so it can show a
# link to /intake. Must be set BEFORE importing it.
os.environ["COMPASS_COMBINED"] = "1"

# employee_interface/app.py does `from auth import ...` and
# `from idea_store import ...`, so its own directory has to be importable.
sys.path.insert(0, str(ROOT / "employee_interface"))

import gradio as gr  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402

from . import app as board_app  # noqa: E402
from . import db, views  # noqa: E402

AUTH_MESSAGE = ("Log in with your employee ID. Credentials are in "
                "TEST_LOGINS.md (run seed/generate_logins.py to recreate it).")


def load_intake():
    """Import the teammate's app, or explain why it could not be loaded.

    Guarded on purpose: if that app ever grows an import that needs an API key
    or a package we do not have, the board must still come up. A broken intake
    tab is an inconvenience; a dead board during a demo is not.
    """
    try:
        import app as intake  # employee_interface/app.py
        return intake.demo, None
    except Exception as error:  # ImportError, missing package, anything
        return None, f"{type(error).__name__}: {error}"


def placeholder(reason: str) -> gr.Blocks:
    with gr.Blocks(title="Idea intake unavailable") as page:
        gr.Markdown(
            "# Idea intake is not available\n\n"
            "The board is running normally at [/](/).\n\n"
            f"`employee_interface/app.py` could not be imported:\n\n"
            f"```\n{reason}\n```")
    return page


def build() -> FastAPI:
    api = FastAPI(title="AI Compass")

    @api.get("/healthz")
    def healthz():
        with db.session() as conn:
            ideas = conn.execute("SELECT COUNT(*) FROM use_cases").fetchone()[0]
        return {"ok": True, "ideas": ideas, "intake": INTAKE_OK}

    @api.get("/intake")
    def intake_no_slash():
        """Starlette mounts the sub-app at /intake/ and does not redirect to it
        here, so /intake alone would 404. People type it without the slash."""
        return RedirectResponse("/intake/")

    @api.get("/submit")
    def submit():
        """Friendlier alias, since 'submit an idea' is what people will type."""
        return RedirectResponse("/intake/")

    gr.mount_gradio_app(api, INTAKE_BLOCKS, path="/intake",
                        auth=views.check_login, auth_message=AUTH_MESSAGE)
    # The board is mounted last, at the root, so it owns "/".
    gr.mount_gradio_app(api, board_app.demo, path="/",
                        auth=views.check_login, auth_message=AUTH_MESSAGE)
    share_sessions(api)
    return api


def share_sessions(api: FastAPI) -> None:
    """Make one login cover both mounted apps.

    Gradio decides who you are from two per-app values: a random `cookie_id`
    that names the cookie, and a `tokens` dict mapping token -> username. Each
    mounted app gets its own pair, so signing in to the board leaves the intake
    chat still asking for a password - which is the two-logins problem this
    file exists to remove.

    Pointing both apps at the same cookie name and the *same dict object* means
    a login on either is a login on both, and the logout button clears both
    (it deletes the token from the shared dict). Nothing is weakened: the same
    `check_login` guards both, and the token is still random per session.
    """
    apps = [r.app for r in api.routes
            if hasattr(getattr(r, "app", None), "cookie_id")]
    if len(apps) < 2:
        return
    first = apps[0]
    for other in apps[1:]:
        other.cookie_id = first.cookie_id
        other.tokens = first.tokens


_blocks, _reason = load_intake()
INTAKE_OK = _blocks is not None
INTAKE_BLOCKS = _blocks if INTAKE_OK else placeholder(_reason or "unknown")


if __name__ == "__main__":
    import uvicorn

    if not views.LOGINS.exists():
        raise SystemExit(
            "No demo logins found. Run: python seed/generate_logins.py")
    with db.session() as connection:
        if not connection.execute(
                "SELECT COUNT(*) FROM use_cases").fetchone()[0]:
            raise SystemExit("No assessed ideas found. Run: python -m seed.load")

    print(f"  board        http://127.0.0.1:{PORT}/")
    print(f"  idea intake  http://127.0.0.1:{PORT}/intake"
          + ("" if INTAKE_OK else f"   UNAVAILABLE: {_reason}"))
    print(f"  one login for both. Credentials: TEST_LOGINS.md")
    if not os.environ.get("OPENAI_API_KEY"):
        print("  note: the intake chat needs OPENAI_API_KEY; the board does not.")
    uvicorn.run(build(), host="127.0.0.1", port=PORT)
