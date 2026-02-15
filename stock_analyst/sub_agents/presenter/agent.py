"""
Presenter agent – renders the final report beautifully.
"""

from google.adk.agents import LlmAgent  # noqa: I001
from tools.config import AI_MODEL, AI_MODEL_NAME

from .prompts import get_instruction as get_presenter_instruction

presenter = LlmAgent(
    name="presenter",
    model=AI_MODEL,
    description="Renders the final report beautifully",
    instruction=get_presenter_instruction(AI_MODEL_NAME),
    output_key="presentation",
)
