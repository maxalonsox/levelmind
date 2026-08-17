from pydantic import BaseModel, ValidationError

from app.ai.planning.contracts import PlanningGoalInput, PlanningLLMProvider
from app.ai.planning.errors import InvalidGeneratedPlanError
from app.models.goal import Goal
from app.schemas.generated_plan import GeneratedPlan


class PlanningService:
    def __init__(self, provider: PlanningLLMProvider) -> None:
        self._provider = provider

    async def generate_plan(self, goal: Goal) -> GeneratedPlan:
        planning_input = PlanningGoalInput(
            title=goal.title,
            current_situation=goal.current_situation,
            expected_outcome=goal.expected_outcome,
            target_timeframe=goal.target_timeframe,
            availability=goal.availability,
        )
        provider_result = await self._provider.generate_plan(planning_input)
        payload = (
            provider_result.model_dump()
            if isinstance(provider_result, BaseModel)
            else provider_result
        )
        try:
            return GeneratedPlan.model_validate(payload)
        except ValidationError as exc:
            raise InvalidGeneratedPlanError(
                "Planning response does not match GeneratedPlan"
            ) from exc
