import asyncio
from typing import Any
from uuid import uuid4

import pytest

from app.ai.planning.contracts import PlanningGoalInput
from app.ai.planning.errors import (
    InvalidGeneratedPlanError,
    PlanningProviderTimeoutError,
)
from app.models.goal import Goal
from app.schemas.generated_plan import GeneratedPlan
from app.services.planning import PlanningService


def valid_generated_plan() -> GeneratedPlan:
    return GeneratedPlan.model_validate(
        {
            "stages": [
                {
                    "title": "Foundation",
                    "order_index": 0,
                    "missions": [
                        {
                            "title": "Build one API",
                            "order_index": 0,
                            "estimated_difficulty": "normal",
                            "tasks": [
                                {
                                    "title": "Implement one endpoint",
                                    "order_index": 0,
                                    "estimated_duration_minutes": 45,
                                    "xp_reward": 10,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )


def planning_goal() -> Goal:
    return Goal(
        id=uuid4(),
        user_id=uuid4(),
        title="Become a backend developer",
        current_situation="I know Python fundamentals",
        expected_outcome="Build production APIs",
        target_timeframe="Six months",
        availability="Eight hours per week",
        status="active",
    )


class StubPlanningProvider:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.received_goal: PlanningGoalInput | None = None

    async def generate_plan(self, goal: PlanningGoalInput) -> GeneratedPlan:
        self.received_goal = goal
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_planning_service_returns_valid_generated_plan() -> None:
    expected_plan = valid_generated_plan()
    provider = StubPlanningProvider(expected_plan)

    result = asyncio.run(PlanningService(provider).generate_plan(planning_goal()))

    assert result == expected_plan


def test_planning_service_minimizes_goal_data() -> None:
    goal = planning_goal()
    provider = StubPlanningProvider(valid_generated_plan())

    asyncio.run(PlanningService(provider).generate_plan(goal))

    assert provider.received_goal is not None
    assert provider.received_goal.model_dump() == {
        "title": goal.title,
        "current_situation": goal.current_situation,
        "expected_outcome": goal.expected_outcome,
        "target_timeframe": goal.target_timeframe,
        "availability": goal.availability,
    }


def test_planning_service_propagates_provider_errors() -> None:
    provider = StubPlanningProvider(
        PlanningProviderTimeoutError("Planning provider timed out")
    )

    with pytest.raises(PlanningProviderTimeoutError):
        asyncio.run(PlanningService(provider).generate_plan(planning_goal()))


def test_planning_service_rejects_invalid_provider_result() -> None:
    provider = StubPlanningProvider({"stages": []})

    with pytest.raises(InvalidGeneratedPlanError):
        asyncio.run(PlanningService(provider).generate_plan(planning_goal()))
