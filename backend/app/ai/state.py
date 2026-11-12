"""Shared state passed between the nodes of the analysis graph."""

import operator
from typing import Annotated, Any, Literal, TypedDict

from app.ai.slices import EvidenceResult, KnowledgeGapResult, SummaryResult
from app.schemas.analysis import (
    ActionResult,
    Analysis,
    IntentResult,
    LanguageResult,
    ResolutionResult,
    RiskResult,
    RootCause,
    SentimentResult,
)

Mode = Literal["live", "replay"]


class AnalysisState(TypedDict, total=False):
    # Inputs
    conversation_id: str
    turns: list[dict[str, Any]]
    mode: Mode

    # Produced by prepare_transcript
    transcript_text: str

    # One key per analysis node
    language: LanguageResult
    intent: IntentResult
    sentiment: SentimentResult
    resolution: ResolutionResult
    evidence: EvidenceResult
    root_cause: RootCause
    risk: RiskResult
    action: ActionResult
    knowledge: KnowledgeGapResult
    summary_score: SummaryResult

    # Produced by validate_output
    analysis: Analysis | None
    retry_node: str | None
    retries: int

    # Accumulates across retries; entries prefixed "warning:" do not block the result.
    errors: Annotated[list[str], operator.add]
