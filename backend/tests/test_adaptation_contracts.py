import pytest
from pydantic import ValidationError

from app.ai.adaptation.contracts import AdaptationProposal


def mission_target() -> dict:
    return {
        "stage_order_index": 0,
        "stage_title": "Backend",
        "mission_order_index": 0,
        "mission_title": "API delivery",
    }


def task_target() -> dict:
    return {
        **mission_target(),
        "task_order_index": 1,
        "task_title": "Implement endpoint",
    }


def proposed_task() -> dict:
    return {
        "title": "Write endpoint tests",
        "description": "Cover success and error responses.",
        "estimated_duration_minutes": 60,
        "xp_reward": 10,
    }


@pytest.mark.parametrize(
    "change",
    [
        {
            "type": "add_task",
            "target": mission_target(),
            "reason": "A prerequisite is missing.",
            "insert_after_task_order_index": 0,
            "task": proposed_task(),
        },
        {
            "type": "split_task",
            "target": task_target(),
            "reason": "The Task combines multiple outcomes.",
            "replacement_tasks": [proposed_task(), proposed_task()],
        },
        {
            "type": "replace_task",
            "target": task_target(),
            "reason": "A focused exercise better addresses the gap.",
            "replacement": proposed_task(),
        },
        {
            "type": "reorder_task",
            "target": task_target(),
            "reason": "The prerequisite should be attempted first.",
            "destination_order_index": 0,
        },
        {
            "type": "adjust_task_difficulty",
            "target": task_target(),
            "reason": "Repeated evidence indicates excessive difficulty.",
            "proposed_difficulty": "easy",
        },
        {
            "type": "adjust_task_duration",
            "target": task_target(),
            "reason": "Observed effort exceeds the estimate.",
            "estimated_duration_minutes": 90,
        },
    ],
)
def test_adaptation_proposal_accepts_each_supported_change(change: dict) -> None:
    proposal = AdaptationProposal.model_validate(
        {
            "decision": "propose_changes",
            "summary": "A bounded change is proposed.",
            "rationale": "The evaluation contains repeated evidence.",
            "changes": [change],
        }
    )

    assert proposal.changes[0].type == change["type"]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "decision": "no_change",
            "summary": "No change.",
            "rationale": "The plan is working.",
            "changes": [
                {
                    "type": "adjust_task_duration",
                    "target": task_target(),
                    "reason": "Invalid with no_change.",
                    "estimated_duration_minutes": 60,
                }
            ],
        },
        {
            "decision": "propose_changes",
            "summary": "Missing change.",
            "rationale": "Invalid decision consistency.",
            "changes": [],
        },
    ],
)
def test_adaptation_proposal_enforces_decision_consistency(payload: dict) -> None:
    with pytest.raises(ValidationError):
        AdaptationProposal.model_validate(payload)


def test_split_task_requires_at_least_two_replacements() -> None:
    with pytest.raises(ValidationError):
        AdaptationProposal.model_validate(
            {
                "decision": "propose_changes",
                "summary": "Split one Task.",
                "rationale": "The Task is too broad.",
                "changes": [
                    {
                        "type": "split_task",
                        "target": task_target(),
                        "reason": "Multiple outcomes were combined.",
                        "replacement_tasks": [proposed_task()],
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "   "),
        ("estimated_duration_minutes", 0),
        ("xp_reward", 0),
    ],
)
def test_proposed_task_rejects_invalid_semantics(field: str, value) -> None:
    task = proposed_task()
    task[field] = value

    with pytest.raises(ValidationError):
        AdaptationProposal.model_validate(
            {
                "decision": "propose_changes",
                "summary": "Add preparation.",
                "rationale": "A prerequisite is missing.",
                "changes": [
                    {
                        "type": "add_task",
                        "target": mission_target(),
                        "reason": "Preparation is required.",
                        "task": task,
                    }
                ],
            }
        )
