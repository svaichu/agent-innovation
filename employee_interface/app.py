"""Employee Interface: employees describe an idea in a chat with the intake agent."""

from dataclasses import dataclass

import gradio as gr
from agents import Agent, RunContextWrapper, Runner, function_tool
from openai.types.responses import ResponseTextDeltaEvent

from auth import check_login, normalize_id
from idea_store import IdeaDraft, employee_name, save_raw_idea, to_markdown

INSTRUCTIONS = """\
You are the intake agent of an internal idea evaluation system. You collect ideas
on how a company process, or the employee's own workflow, can be improved.

Before an idea can be submitted you need all of this:
- scope: a company process, or the employee's own workflow
- the current process: how it works today
- the problem with it
- the proposed improvement
- who is affected
- the expected benefit, for example time saved or fewer errors

Rules:
- Check what the employee has already said, then ask for what is missing or too
  vague to understand. Ask one short question at a time.
- Use only what the employee said. Never invent or embellish details. If they do
  not know something after being asked, record it as unknown.
- If an idea is not about improving a process or workflow, say that this is what
  is being collected and ask which process it would improve.
- Ask the employee to leave out personal data about colleagues or customers and
  confidential details, and never put them in a draft.
- Do not score or judge the idea.
- When nothing is missing, call propose_idea. The draft is then shown below your
  reply, so do not repeat it. Ask the employee to check it and press "Submit
  idea", or to say what to change.
- You cannot submit ideas yourself. Only the button stores them. Call
  propose_idea again after any change, or if the employee confirms in the chat,
  so that the draft and button are shown.
- Reply and write the draft in the employee's language.
"""


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


# No model is set, so the SDK default applies (override: OPENAI_DEFAULT_MODEL).
intake_agent = Agent[IntakeContext](
    name="Intake", instructions=INSTRUCTIONS, tools=[propose_idea]
)


def to_text(content) -> str:
    """Gradio history content is a string or a list of content parts."""
    if isinstance(content, str):
        return content
    return "".join(part["text"] for part in content if part.get("type") == "text")


async def respond(message: str, history: list[dict]):
    """Stream the agent's reply. Also yields the draft and the submit button state."""
    hidden = gr.update(visible=False)
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


def signed_in_as(request: gr.Request) -> str:
    employee_id = normalize_id(request.username or "")
    return f"Signed in as **{employee_name(employee_id) or 'unknown'}** ({employee_id})"


def submit_idea(draft: IdeaDraft | None, history: list[dict], request: gr.Request):
    """Store the draft the employee is looking at. Runs only on the button."""
    unchanged = (gr.skip(), gr.skip(), gr.skip(), gr.skip())
    if draft is None:
        return unchanged
    # The author is whoever logged in; the employee cannot choose it.
    employee_id = normalize_id(request.username or "")
    if not employee_name(employee_id):
        gr.Warning("Your login does not match an employee, so nothing was submitted.")
        return unchanged

    idea_id = save_raw_idea(draft, author_id=employee_id)
    confirmation = f"Your idea has been submitted as **{idea_id}**. Thank you!"
    history = history + [{"role": "assistant", "content": confirmation}]
    return history, history, None, gr.update(visible=False)


with gr.Blocks(title="Employee Interface", fill_height=True) as demo:
    gr.Markdown(
        "# Employee Interface\n"
        "How could a company process or your own workflow be improved? "
        "The assistant asks for anything missing before you submit."
    )
    with gr.Row(equal_height=True):
        user_label = gr.Markdown()
        gr.Button("Log out", link="/logout?all_session=false", size="sm", scale=0)
    demo.load(signed_in_as, outputs=user_label)
    draft = gr.State(None)
    submit_button = gr.Button(
        "Submit idea", variant="primary", visible=False, render=False
    )
    chat = gr.ChatInterface(
        fn=respond,
        textbox=gr.Textbox(placeholder="Type your idea here...", submit_btn=True),
        additional_outputs=[draft, submit_button],
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

if __name__ == "__main__":
    demo.launch(auth=check_login, auth_message="Log in with your employee ID.")
