"""The merge agent: reads all ideas and proposes refined ideas that combine them."""

from dataclasses import dataclass
from pathlib import Path

from agents import Agent, OpenAIProvider, RunConfig, Runner
from openai import AsyncOpenAI
from pydantic import BaseModel

from idea_store import IdeaDraft
from score_agent import list_documents, read_document

INSTRUCTIONS = (Path(__file__).resolve().parent / "merge_prompt.md").read_text(
    encoding="utf-8"
)


class MergeProposal(BaseModel):
    # The ID of the refined idea to rewrite. Empty for a new one.
    revises: str | None
    source_ids: list[str]
    draft: IdeaDraft
    rationale: str
    differences: list[str]


class MergeProposals(BaseModel):
    proposals: list[MergeProposal]


@dataclass
class MergeContext:
    documents: dict[str, str]


merge_agent = Agent[MergeContext](
    name="Merge",
    instructions=INSTRUCTIONS,
    tools=[list_documents, read_document],
    output_type=MergeProposals,
)


async def propose_merges(
    prompt: str, context: MergeContext, model: str
) -> list[MergeProposal]:
    """Run the agent once on all ideas."""
    # Its own client: merging runs outside the event loop of the web app.
    async with AsyncOpenAI() as client:
        result = await Runner.run(
            merge_agent.clone(model=model),
            prompt,
            context=context,
            max_turns=25,
            run_config=RunConfig(model_provider=OpenAIProvider(openai_client=client)),
        )
    return result.final_output.proposals
