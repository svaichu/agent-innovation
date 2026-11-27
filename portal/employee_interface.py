"""Employee Interface: employees describe an idea in a chat with the intake agent."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import gradio as gr
import psycopg
import yaml
from agents import Agent, RunContextWrapper, Runner, function_tool
from openai.types.responses import ResponseTextDeltaEvent

from auth import find_employee
from idea_store import (
    IdeaDraft,
    RawIdea,
    list_raw_ideas,
    save_raw_idea,
    to_markdown,
    update_raw_idea,
)

PORTAL_DIR = Path(__file__).resolve().parent
INSTRUCTIONS = (PORTAL_DIR / "intake_prompt.md").read_text(encoding="utf-8")
CONFIG = yaml.safe_load((PORTAL_DIR / "config.yaml").read_text(encoding="utf-8"))


@dataclass
class Proposal:
    """A draft waiting for the button: a new idea, or a new version of one."""

    draft: IdeaDraft
    revises: str | None = None


@dataclass
class IntakeContext:
    # From the login. The tools reach only this employee's ideas.
    author_id: str | None
    proposal: Proposal | None = None
    # Stored ideas to display below the reply, by ID.
    shown: dict[str, RawIdea] = field(default_factory=dict)


def own_ideas(author_id: str | None) -> dict[str, RawIdea] | None:
    """The employee's ideas by ID, newest first. None if they cannot be loaded."""
    if not author_id:
        return None
    try:
        return {idea.id: idea for idea in list_raw_ideas(author_id)}
    except psycopg.Error:
        logging.exception("Could not load the ideas of an employee")
        return None


UNAVAILABLE = "The employee's ideas cannot be loaded right now."


@function_tool
def list_my_ideas(context: RunContextWrapper[IntakeContext]) -> str:
    """List the ideas this employee has submitted, newest first."""
    ideas = own_ideas(context.context.author_id)
    if ideas is None:
        return UNAVAILABLE
    if not ideas:
        return "The employee has not submitted any ideas yet."
    return "\n".join(
        f"{idea.id} | {idea.text.partition(chr(10))[0].removeprefix('# ')} | "
        f"submitted {idea.created_at:%Y-%m-%d} | version {idea.version}"
        for idea in ideas.values()
    )


@function_tool
def show_my_idea(context: RunContextWrapper[IntakeContext], idea_id: str) -> str:
    """Show the employee the full stored text of one of their submitted ideas.

    Args:
        idea_id: The ID of the idea, such as RI-0001.
    """
    ideas = own_ideas(context.context.author_id)
    if ideas is None:
        return UNAVAILABLE
    if not (idea := ideas.get(idea_id.strip().upper())):
        return f"The employee has no idea with the ID {idea_id}."
    context.context.shown[idea.id] = idea
    return f"Shown below your reply. Stored text of {idea.id}:\n\n{idea.text}"


@function_tool
def propose_idea(
    context: RunContextWrapper[IntakeContext],
    draft: IdeaDraft,
    revises: str | None = None,
) -> str:
    """Show the employee a complete idea draft to check and submit.

    Args:
        draft: The idea. Every field must be filled from what the employee said,
            now or in the stored idea being revised.
        revises: The ID of the submitted idea this draft improves. Empty for a new
            idea.
    """
    if missing := draft.missing_fields():
        return f"Not shown. Ask the employee about: {', '.join(missing)}."
    if revises := (revises or "").strip().upper() or None:
        ideas = own_ideas(context.context.author_id)
        if ideas is None:
            return f"Not shown. {UNAVAILABLE}"
        if revises not in ideas:
            return f"Not shown. The employee has no idea with the ID {revises}."
    context.context.proposal = Proposal(draft, revises)
    return "The draft is shown below your reply. It is not stored yet."


intake_agent = Agent[IntakeContext](
    name="Intake",
    instructions=INSTRUCTIONS,
    model=CONFIG["models"]["intake_agent"],
    tools=[list_my_ideas, show_my_idea, propose_idea],
)


def to_text(content) -> str:
    """Gradio history content is a string or a list of content parts."""
    if isinstance(content, str):
        return content
    return "".join(part["text"] for part in content if part.get("type") == "text")


def check_message(message: str):
    """Reject a blank message before it reaches the chat."""
    return gr.validate(bool(message.strip()), "Please describe your idea.")


async def respond(message: str, history: list[dict], request: gr.Request):
    """Stream the agent's reply. Also yields the proposal and the button state."""
    hidden = gr.update(visible=False)
    # The chat box validates first, but the API calls this function directly.
    if not message.strip():
        yield "Please describe your idea.", None, hidden
        return

    items = [{"role": m["role"], "content": to_text(m["content"])} for m in history]
    items.append({"role": "user", "content": message})

    # A new message makes any earlier draft outdated, so withdraw it right away.
    yield "", None, hidden

    employee = find_employee(request.username or "")
    context = IntakeContext(author_id=employee["id"] if employee else None)
    result = Runner.run_streamed(intake_agent, items, context=context)
    reply = ""
    async for event in result.stream_events():
        if event.type == "raw_response_event" and isinstance(
            event.data, ResponseTextDeltaEvent
        ):
            reply += event.data.delta
            yield reply, None, hidden

    # Appended to the reply, so the agent sees these texts in later turns.
    for idea in context.shown.values():
        reply += (
            f"\n\n---\n\n**Submitted idea {idea.id}** "
            f"(version {idea.version})\n\n{idea.text}"
        )
    button = hidden
    if proposal := context.proposal:
        label = "Submit idea"
        heading = ""
        if proposal.revises:
            label = f"Update idea {proposal.revises}"
            heading = f"**New version of {proposal.revises}, not saved yet**\n\n"
        reply += f"\n\n---\n\n{heading}{to_markdown(proposal.draft)}"
        button = gr.update(value=label, visible=True)
    if context.shown or context.proposal:
        yield reply, context.proposal, button


def submit_idea(proposal: Proposal | None, history: list[dict], request: gr.Request):
    """Store the draft the employee is looking at. Runs only on the button."""
    unchanged = (gr.skip(), gr.skip(), gr.skip(), gr.skip())
    if proposal is None:
        return unchanged
    # The author is whoever logged in; the employee cannot choose it.
    if not (employee := find_employee(request.username or "")):
        gr.Warning("Your login does not match an employee, so nothing was submitted.")
        return unchanged

    try:
        if idea_id := proposal.revises:
            if not update_raw_idea(idea_id, proposal.draft, author_id=employee["id"]):
                gr.Warning(f"You have no idea {idea_id}, so nothing was changed.")
                return unchanged
            confirmation = f"Your idea **{idea_id}** has been updated. Thank you!"
        else:
            idea_id = save_raw_idea(proposal.draft, author_id=employee["id"])
            confirmation = f"Your idea has been submitted as **{idea_id}**. Thank you!"
    except psycopg.Error:
        logging.exception("Could not save an idea")
        gr.Warning("The idea could not be saved. Please try again in a moment.")
        return unchanged
    history = history + [{"role": "assistant", "content": confirmation}]
    return history, history, None, gr.update(visible=False)


def build() -> None:
    """Add the employee page to the page being built."""
    gr.Markdown(
        "# Employee Interface\n"
        "How could a company process or your own workflow be improved? "
        "The assistant asks for anything missing before you submit. "
        "You can also ask to see your submitted ideas and improve them."
    )
    proposal = gr.State(None)
    submit_button = gr.Button(
        "Submit idea", variant="primary", visible=False, render=False
    )
    chat = gr.ChatInterface(
        fn=respond,
        textbox=gr.Textbox(placeholder="Type your idea here...", submit_btn=True),
        additional_outputs=[proposal, submit_button],
        validator=check_message,
    )
    submit_button.render()

    # chatbot_state is the history ChatInterface passes to respond().
    submit_button.click(
        submit_idea,
        inputs=[proposal, chat.chatbot_state],
        outputs=[chat.chatbot, chat.chatbot_state, proposal, submit_button],
    )
    # Clearing or undoing the chat also withdraws the draft.
    for chat_event in (chat.chatbot.clear, chat.chatbot.undo):
        chat_event(
            lambda: (None, gr.update(visible=False)), outputs=[proposal, submit_button]
        )
