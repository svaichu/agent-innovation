"""The score agent: reads one idea and the knowledge base, and fills the inputs."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agents import Agent, OpenAIProvider, RunConfig, RunContextWrapper, Runner, function_tool
from openai import AsyncOpenAI
from pydantic import BaseModel

INSTRUCTIONS = (Path(__file__).resolve().parent / "score_prompt.md").read_text(
    encoding="utf-8"
)


class InputValue(BaseModel):
    name: str
    value: float | None
    source: Literal["employee", "knowledge_base", "estimate"] | None
    evidence: str | None
    basis: list[str]


class FitAnswers(BaseModel):
    low_volume_low_value: bool | None
    structured_input: bool | None
    rule_expressible: bool | None
    needs_judgement: bool | None
    unstructured_or_language: bool | None
    deterministic_required: bool | None
    prediction_task: bool | None
    has_historical_data: bool | None


class ActAnswers(BaseModel):
    art5_practices: list[str] | None
    annex_i_safety_component: bool | None
    annex_iii_area: str | None
    profiles_people: bool | None
    narrow_or_preparatory: bool | None
    art50: list[str] | None


class ScoreInputs(BaseModel):
    """What the agent returns. The names of the inputs come from the metric file."""

    inputs: list[InputValue]
    open_questions: list[str]
    fit_answers: FitAnswers
    act_answers: ActAnswers


@dataclass
class ScoreContext:
    documents: dict[str, str]
    metric_text: str
    checks_text: str


@function_tool
def list_documents(context: RunContextWrapper[ScoreContext]) -> str:
    """List the knowledge base documents you can read."""
    return "\n".join(sorted(context.context.documents))


@function_tool
def read_document(context: RunContextWrapper[ScoreContext], path: str) -> str:
    """Read one knowledge base document.

    Args:
        path: A path from list_documents, such as it/systems.csv.
    """
    name = path.strip().removeprefix("knowledge-base/")
    return context.context.documents.get(name, f"Not available: {path}")


def instructions(context: RunContextWrapper[ScoreContext], agent: Agent) -> str:
    files = context.context
    return (
        f"{INSTRUCTIONS}\n\n# Metric file\n\n{files.metric_text}\n\n"
        f"# Checks file\n\n{files.checks_text}"
    )


score_agent = Agent[ScoreContext](
    name="Score",
    instructions=instructions,
    tools=[list_documents, read_document],
    output_type=ScoreInputs,
)


async def fill_inputs(idea: str, context: ScoreContext, model: str) -> ScoreInputs:
    """Run the agent on one idea."""
    # The idea cannot close its own tag.
    tagged = idea.replace("</idea>", "")
    # Its own client: scoring runs outside the event loop of the web app.
    async with AsyncOpenAI() as client:
        result = await Runner.run(
            score_agent.clone(model=model),
            f"<idea>\n{tagged}\n</idea>",
            context=context,
            max_turns=25,
            run_config=RunConfig(model_provider=OpenAIProvider(openai_client=client)),
        )
    return result.final_output
