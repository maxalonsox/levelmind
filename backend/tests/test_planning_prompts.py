import json

from app.ai.planning.contracts import PlanningGoalInput
from app.ai.planning.prompts import (
    PLANNING_SYSTEM_PROMPT,
    build_planning_prompt,
)
from app.schemas.generated_plan import GeneratedPlan


def _prompt() -> str:
    return " ".join(PLANNING_SYSTEM_PROMPT.lower().split())


def test_prompt_treats_availability_as_capacity_not_quota() -> None:
    prompt = _prompt()

    assert "maximum capacity" in prompt
    assert "never as a quota or obligation to fill" in prompt
    assert "do not make task durations add up" in prompt
    assert "debugging" in prompt
    assert "future adaptation" in prompt


def test_prompt_treats_timeframe_as_scope_horizon_not_calendar() -> None:
    prompt = _prompt()

    assert "planning horizon for scope and depth" in prompt
    assert "not as a calendar" in prompt
    assert "specific days" in prompt
    assert "mandatory numbered weeks" in prompt
    assert "artificial deadlines" in prompt


def test_prompt_is_gap_aware_without_requesting_internal_reasoning() -> None:
    prompt = _prompt()

    assert "gap between current_situation and expected_outcome" in prompt
    assert "current_situation" in prompt
    assert "expected_outcome" in prompt
    assert "target_timeframe" in prompt
    assert "reason internally" not in prompt


def test_prompt_requires_executable_verifiable_tasks() -> None:
    prompt = _prompt()

    assert "one focused work session" in prompt
    assert "one independently verifiable result" in prompt
    assert "completion evidence" in prompt
    assert "30, 45, 60, 90, or 120" in prompt


def test_prompt_requires_large_activities_to_be_split() -> None:
    prompt = _prompt()

    assert "multiple sessions" in prompt
    assert "independent objectives" in prompt
    assert "split it into multiple tasks" in prompt
    assert "multi-component integration" in prompt


def test_prompt_prioritizes_prerequisites_through_order_index() -> None:
    prompt = _prompt()

    assert "use order_index" in prompt
    assert "essential prerequisites" in prompt
    assert "before complementary, specialized, optional, or advanced" in prompt
    assert "prerequisites are already covered" in prompt


def test_prompt_avoids_trendy_tools_and_artificial_plan_growth() -> None:
    prompt = _prompt()

    assert "transferable knowledge and foundations" in prompt
    assert "fashionable tools" in prompt
    assert "directly close an identified gap" in prompt
    assert "never generate hundreds of tasks" in prompt
    assert "prefer fewer well-designed tasks" in prompt


def test_prompt_requires_natural_spanish_without_translating_schema() -> None:
    prompt = _prompt()

    assert "every natural-language field visible to the user" in prompt
    assert "natural spanish" in prompt
    assert "stage, mission, and task title and description" in prompt
    assert "json keys, enum values, difficulty values" in prompt
    assert "do not translate them" in prompt
    assert "professional but approachable" in prompt
    assert "do not provide chain-of-thought" in prompt

    request = build_planning_prompt(
        PlanningGoalInput(
            title="Aprender backend",
            current_situation="Conozco Python",
            expected_outcome="Crear APIs",
            target_timeframe=None,
            availability=None,
        )
    )
    schema_marker = "The response must match this JSON Schema:\n"
    assert schema_marker in request.user
    supplied_schema = json.loads(request.user.split(schema_marker, maxsplit=1)[1])
    assert supplied_schema == GeneratedPlan.model_json_schema()
