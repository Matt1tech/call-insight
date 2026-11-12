"""LangGraph workflow that turns a transcript into a validated ``Analysis``.

Graph: prepare_transcript -> classify_language -> classify_intent -> analyse_sentiment ->
assess_resolution -> extract_evidence -> analyse_root_cause -> predict_risks ->
recommend_action -> detect_knowledge_gaps -> summarise_and_score -> validate_output.
After validation a conditional edge either ends the run or, in live mode only and at most
once, sends it back to the node that failed (downstream nodes then run again).
"""

import json
from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.ai.llm_client import get_chat_model
from app.ai.nodes import NODE_SPECS, make_analysis_node, prepare_transcript, validate_output
from app.ai.state import AnalysisState, Mode
from app.schemas.analysis import Analysis

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TRANSCRIPTS_PATH = DATA_DIR / "transcripts" / "transcripts.json"
REVIEWED_PATH = DATA_DIR / "analysis" / "analysis.json"


def load_transcripts(path: Path = TRANSCRIPTS_PATH) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in json.loads(path.read_text(encoding="utf-8"))}


def load_reviewed(path: Path = REVIEWED_PATH) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in json.loads(path.read_text(encoding="utf-8"))}


def build_graph(
    mode: Mode = "replay",
    model: Any | None = None,
    reviewed: dict[str, dict[str, Any]] | None = None,
):
    """Build and compile the analysis graph for the given mode."""
    reviewed = reviewed if reviewed is not None else (load_reviewed() if mode == "replay" else {})
    graph = StateGraph(AnalysisState)

    graph.add_node("prepare_transcript", prepare_transcript)
    for spec in NODE_SPECS:
        graph.add_node(spec.name, make_analysis_node(spec, mode, model, reviewed))
    graph.add_node("validate_output", validate_output)

    order = ["prepare_transcript", *[s.name for s in NODE_SPECS], "validate_output"]
    graph.add_edge(START, order[0])
    for current, following in zip(order, order[1:], strict=False):
        graph.add_edge(current, following)

    retry_targets = {s.name: s.name for s in NODE_SPECS}
    graph.add_conditional_edges(
        "validate_output",
        lambda state: state.get("retry_node") or END,
        {**retry_targets, END: END},
    )
    return graph.compile()


class AnalysisRun(BaseModel):
    analysis: Analysis | None
    mode: Literal["live", "replay"]
    errors: list[str]
    retries: int

    @property
    def blocking_errors(self) -> list[str]:
        return [e for e in self.errors if not e.startswith("warning:")]


def resolve_mode(mode: str = "auto", model: Any | None = None) -> tuple[Mode, Any | None]:
    if mode == "replay":
        return "replay", None
    model = model if model is not None else get_chat_model()
    if mode == "live":
        if model is None:
            raise RuntimeError(
                "live mode needs CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN and CLOUDFLARE_MODEL"
            )
        return "live", model
    if mode == "auto":
        return ("live", model) if model is not None else ("replay", None)
    raise ValueError(f"unknown mode: {mode}")


def run_analysis(
    conversation: str | dict[str, Any],
    mode: str = "auto",
    model: Any | None = None,
) -> AnalysisRun:
    """Analyse one conversation, given by id or as a dict with ``id`` and ``turns``."""
    if isinstance(conversation, str):
        conversation = load_transcripts()[conversation]
    resolved, chat_model = resolve_mode(mode, model)
    app = build_graph(resolved, chat_model)
    final = app.invoke(
        {
            "conversation_id": conversation["id"],
            "turns": conversation["turns"],
            "mode": resolved,
            "errors": [],
        }
    )
    return AnalysisRun(
        analysis=final.get("analysis"),
        mode=resolved,
        errors=final.get("errors", []),
        retries=final.get("retries", 0),
    )
