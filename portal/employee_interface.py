"""Employee Interface: employees describe an idea in a chat with the intake agent."""

import logging
from dataclasses import dataclass
from pathlib import Path

import gradio as gr
import psycopg
import yaml
from agents import Agent, RunContextWrapper, Runner, function_tool
from openai.types.responses import ResponseTextDeltaEvent

from auth import find_employee
from idea_store import IdeaDraft, save_raw_idea, to_markdown

PORTAL_DIR = Path(__file__).resolve().parent
INSTRUCTIONS = (PORTAL_DIR / "intake_prompt.md").read_text(encoding="utf-8")
CONFIG = yaml.safe_load((PORTAL_DIR / "config.yaml").read_text(encoding="utf-8"))


@dataclass
class IntakeContext:
    draft: IdeaDraft | None = None


@function_tool
def propose_idea(context: RunContextWrapper[IntakeContext], draft: IdeaDraft) -> str:
    """Show the employee a complete idea draft to check and submit.

    Args:
        draft: The idea. Every field must be filled from what the employee said.
    """
    if missing := draft.missing_fields():
        return f"Not shown. Ask the employee about: {', '.join(missing)}."
    context.context.draft = draft
    return "The draft is shown below your reply. It is not stored yet."


intake_agent = Agent[IntakeContext](
    name="Intake",
    instructions=INSTRUCTIONS,
    model=CONFIG["models"]["intake_agent"],
    tools=[propose_idea],
)


def to_text(content) -> str:
    """Gradio history content is a string or a list of content parts."""
    if isinstance(content, str):
        return content
    return "".join(part["text"] for part in content if part.get("type") == "text")


def check_message(message: str):
    """Reject a blank message before it reaches the chat."""
    return gr.validate(bool(message.strip()), "Please describe your idea.")


async def respond(message: str, history: list[dict]):
    """Stream the agent's reply. Also yields the draft and the submit button state."""
    hidden = gr.update(visible=False)
    # The chat box validates first, but the API calls this function directly.
    if not message.strip():
        yield "Please describe your idea.", None, hidden
        return

    items = [{"role": m["role"], "content": to_text(m["content"])} for m in history]
    items.append({"role": "user", "content": message})

    # A new message makes any earlier draft outdated, so withdraw it right away.
    yield "", None, hidden

    context = IntakeContext()
    result = Runner.run_streamed(intake_agent, items, context=context)
    reply = ""
    async for event in result.stream_events():
        if event.type == "raw_response_event" and isinstance(
            event.data, ResponseTextDeltaEvent
        ):
            reply += event.data.delta
            yield reply, None, hidden

    if context.draft:
        # Part of the reply, so the agent sees the draft in later turns.
        reply += f"\n\n---\n\n{to_markdown(context.draft)}"
        yield reply, context.draft, gr.update(visible=True)


def submit_idea(draft: IdeaDraft | None, history: list[dict], request: gr.Request):
    """Store the draft the employee is looking at. Runs only on the button."""
    unchanged = (gr.skip(), gr.skip(), gr.skip(), gr.skip())
    if draft is None:
        return unchanged
    # The author is whoever logged in; the employee cannot choose it.
    if not (employee := find_employee(request.username or "")):
        gr.Warning("Your login does not match an employee, so nothing was submitted.")
        return unchanged

    try:
        idea_id = save_raw_idea(draft, author_id=employee["id"])
    except psycopg.Error:
        logging.exception("Could not save an idea")
        gr.Warning("The idea could not be saved. Please try again in a moment.")
        return unchanged
    confirmation = f"Your idea has been submitted as **{idea_id}**. Thank you!"
    history = history + [{"role": "assistant", "content": confirmation}]
    return history, history, None, gr.update(visible=False)


def build() -> None:
    """Add the employee page to the page being built."""
    gr.Markdown(
        "# Employee Interface\n"
        "How could a company process or your own workflow be improved? "
        "The assistant asks for anything missing before you submit."
    )
    draft = gr.State(None)
    submit_button = gr.Button(
        "Submit idea", variant="primary", visible=False, render=False
    )
    chat = gr.ChatInterface(
        fn=respond,
        textbox=gr.Textbox(placeholder="Type your idea here...", submit_btn=True),
        additional_outputs=[draft, submit_button],
        validator=check_message,
    )
    submit_button.render()

    # chatbot_state is the history ChatInterface passes to respond().
    submit_button.click(
        submit_idea,
        inputs=[draft, chat.chatbot_state],
        outputs=[chat.chatbot, chat.chatbot_state, draft, submit_button],
    )
    # Clearing or undoing the chat also withdraws the draft.
    for chat_event in (chat.chatbot.clear, chat.chatbot.undo):
        chat_event(
            lambda: (None, gr.update(visible=False)), outputs=[draft, submit_button]
        )
