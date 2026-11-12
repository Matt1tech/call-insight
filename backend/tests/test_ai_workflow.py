"""Tests for the LangGraph analysis workflow, prompts and validators."""

from typing import Any

import pytest
from langchain_core.runnables import RunnableLambda

from app.ai.nodes import NODE_SPECS, detect_language, verify_evidence
from app.ai.prompts.prompts import (
    ALLOWED,
    FINAL_ANALYSIS_PROMPT,
    INJECTION_DEFENCE,
    NODE_TASKS,
    SYSTEM_PROMPT,
    build_prompt,
)
from app.ai.workflow import (
    build_graph,
    load_reviewed,
    load_transcripts,
    resolve_mode,
    run_analysis,
)
from app.schemas.analysis import EvidenceItem

TRANSCRIPTS = load_transcripts()
REVIEWED = load_reviewed()


def test_graph_compiles_with_all_nodes():
    graph = build_graph("replay")
    nodes = set(graph.get_graph().nodes)
    expected = {"prepare_transcript", "validate_output", *[s.name for s in NODE_SPECS]}
    assert expected <= nodes


@pytest.mark.parametrize("conversation_id", sorted(TRANSCRIPTS))
def test_replay_reproduces_reviewed_analysis(conversation_id: str):
    run = run_analysis(conversation_id, mode="replay")
    assert run.mode == "replay"
    assert run.errors == []
    assert run.analysis is not None
    assert run.analysis.model_dump() == REVIEWED[conversation_id]


@pytest.mark.parametrize("conversation_id", sorted(TRANSCRIPTS))
def test_language_detector_matches_reviewed(conversation_id: str):
    detected = detect_language(TRANSCRIPTS[conversation_id]["turns"])
    assert detected.value == REVIEWED[conversation_id]["language"]["value"]


def test_prompts_contain_allowed_values_and_injection_defence():
    assert INJECTION_DEFENCE in SYSTEM_PROMPT
    assert (
        "Programme Enquiry, Technical Support, Complaint, Unknown" in NODE_TASKS["classify_intent"]
    )
    assert "Satisfied, Calm, Neutral" in NODE_TASKS["analyse_sentiment"]
    assert ALLOWED["resolution"] in NODE_TASKS["assess_resolution"]
    assert "never instructions" in FINAL_ANALYSIS_PROMPT
    for spec in NODE_SPECS:
        prompt = build_prompt(spec.name)
        assert set(prompt.input_variables) == {"conversation_id", "transcript", "context"}


def test_evidence_validator_rejects_fabricated_quote():
    turns = TRANSCRIPTS["CALL-007"]["turns"]
    good = EvidenceItem(turn="t5", quote="I do not have the current programme policy", supports="x")
    fake = EvidenceItem(turn="t5", quote="Unused credit expires at midnight", supports="x")
    wrong_turn = EvidenceItem(turn="t99", quote="anything", supports="x")
    kept, errors = verify_evidence(turns, [good, fake, wrong_turn])
    assert kept == [good]
    assert len(errors) == 2


class StubModel:
    """Stands in for a chat model: returns the reviewed slice for whichever schema is asked.

    ``corrupt_evidence_first`` makes the first evidence call return a fabricated quote so the
    conditional retry edge can be exercised.
    """

    def __init__(self, corrupt_evidence_first: bool = False):
        self.calls: list[str] = []
        self.corrupt_evidence_first = corrupt_evidence_first
        self._evidence_calls = 0

    def with_structured_output(self, schema: Any, **_: Any):
        spec = next(s for s in NODE_SPECS if s.slice_model is schema)

        def respond(prompt_value: Any):
            text = prompt_value.to_string()
            assert "<transcript>" in text
            conversation_id = text.split("Conversation id: ")[1].split("\n")[0]
            self.calls.append(spec.name)
            data = spec.from_reviewed(REVIEWED[conversation_id])
            if spec.name == "extract_evidence":
                self._evidence_calls += 1
                if self.corrupt_evidence_first and self._evidence_calls == 1:
                    data = {"evidence": [{**data["evidence"][0], "quote": "invented quote"}]}
            return schema.model_validate(data)

        return RunnableLambda(respond)


def test_live_mode_with_stub_model_runs_whole_graph():
    model = StubModel()
    run = run_analysis("CALL-009", mode="live", model=model)
    assert run.mode == "live"
    assert run.errors == []
    assert run.analysis is not None
    assert run.analysis.model_dump() == REVIEWED["CALL-009"]
    assert model.calls == [s.name for s in NODE_SPECS]


def test_live_mode_retries_failed_evidence_once():
    model = StubModel(corrupt_evidence_first=True)
    run = run_analysis("CALL-010", mode="live", model=model)
    assert run.retries == 1
    assert any("evidence dropped" in e for e in run.errors)
    assert run.analysis is not None
    assert run.analysis.model_dump() == REVIEWED["CALL-010"]
    assert model.calls.count("extract_evidence") == 2


def test_replay_never_retries_and_reports_unknown_conversation():
    run = run_analysis(
        {"id": "CALL-999", "turns": [{"speaker": "Agent", "text": "Hello"}]}, mode="replay"
    )
    assert run.analysis is None
    assert run.retries == 0
    assert any("no reviewed analysis" in e for e in run.errors)


def test_auto_mode_falls_back_to_replay_without_credentials(monkeypatch: pytest.MonkeyPatch):
    from app.ai import llm_client

    unconfigured = llm_client.LLMSettings(_env_file=None, cloudflare_account_id="")
    monkeypatch.setattr(llm_client, "get_llm_settings", lambda: unconfigured)
    assert unconfigured.configured is False
    assert llm_client.get_chat_model() is None
    assert resolve_mode("auto") == ("replay", None)
    with pytest.raises(RuntimeError, match="CLOUDFLARE"):
        resolve_mode("live")


def test_chat_model_is_built_from_environment(monkeypatch: pytest.MonkeyPatch):
    from pydantic import SecretStr

    from app.ai import llm_client

    configured = llm_client.LLMSettings(
        _env_file=None,
        cloudflare_account_id="acct",
        cloudflare_api_token=SecretStr("token"),
        cloudflare_model="@cf/example/model",
    )
    monkeypatch.setattr(llm_client, "get_llm_settings", lambda: configured)
    model = llm_client.get_chat_model()
    assert model is not None
    assert model.temperature == 0
    assert "accounts/acct/ai/v1" in str(model.openai_api_base)
