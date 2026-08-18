from app.ai.adaptation.prompts import ADAPTATION_SYSTEM_PROMPT


def test_adaptation_prompt_requires_minimal_evidence_based_changes() -> None:
    prompt = " ".join(ADAPTATION_SYSTEM_PROMPT.lower().split())

    assert "minimal effective adaptation" in prompt
    assert "ground every rationale and change reason in observed signals" in prompt
    assert "do not invent problems" in prompt
    assert "preserve parts of the plan that work" in prompt
    assert "one isolated difficulty" in prompt
    assert "preserve prerequisites" in prompt
    assert "do not add work merely to fill availability" in prompt
    assert "one verifiable result" in prompt
    assert "never use uuids" in prompt
    assert "factual historical evidence" in prompt
    assert "not a declared preference" in prompt
    assert "in spanish" in prompt
    assert "one or two short, direct sentences" in prompt
    assert "at most three short sentences" in prompt
    assert "each change reason to one short sentence" in prompt
    assert "never mention internal status or contract names" in prompt
    assert "insufficient_data" in prompt
    assert "do not provide chain-of-thought" in prompt
    assert "return only one json object" in prompt
