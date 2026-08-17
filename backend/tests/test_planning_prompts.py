from app.ai.planning.prompts import PLANNING_SYSTEM_PROMPT


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


def test_prompt_requires_implicit_gap_analysis() -> None:
    prompt = _prompt()

    assert "current state -> gap -> target state" in prompt
    assert "current_situation" in prompt
    assert "expected_outcome" in prompt
    assert "target_timeframe" in prompt
    assert "do not return this analysis" in prompt


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
