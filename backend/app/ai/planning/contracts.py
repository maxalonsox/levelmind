from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.schemas.generated_plan import GeneratedPlan


class PlanningGoalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    current_situation: str
    expected_outcome: str
    target_timeframe: str | None
    availability: str | None


class PlanningLLMProvider(Protocol):
    async def generate_plan(self, goal: PlanningGoalInput) -> GeneratedPlan:
        """Generate and validate a plan without persisting it."""
        ...
