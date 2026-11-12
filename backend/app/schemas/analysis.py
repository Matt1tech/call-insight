"""Pydantic schemas for the structured conversation analysis.

Each slice model matches the output of one node in the analysis workflow, and
``Analysis`` is the final merged record stored in ``data/analysis/analysis.json``.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["English", "Bahasa Malaysia", "Mixed", "Unknown"]
Intent = Literal["Programme Enquiry", "Technical Support", "Complaint", "Unknown"]
Sentiment = Literal["Positive", "Neutral", "Negative", "Unknown"]
Emotion = Literal["Happy", "Angry", "Frustrated", "Confused", "Concerned", "Neutral", "Unknown"]
Tone = Literal[
    "Satisfied", "Calm", "Neutral", "Confused", "Concerned", "Frustrated", "Angry", "Unknown"
]
Level = Literal["Low", "Medium", "High", "Unknown"]
Resolution = Literal["Resolved", "Unresolved", "Unknown"]
Escalation = Literal["Yes", "No", "Unknown"]
ConfidenceLevel = Literal["Low", "Medium", "High"]
Priority = Literal["Low", "Medium", "High", "Urgent"]
GapKind = Literal[
    "unsupported_claim",
    "missing_programme_info",
    "unverified_statement",
    "unknown_cause",
    "needs_verification",
]

# Ordering used to derive overall risk (highest of the two risk levels).
LEVEL_ORDER: dict[str, int] = {"Unknown": 0, "Low": 1, "Medium": 2, "High": 3}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LanguageResult(_Strict):
    value: Language
    basis: str


class IntentResult(_Strict):
    value: Intent
    reason: str


class SentimentResult(_Strict):
    sentiment: Sentiment
    emotion: Emotion
    tone: Tone
    reason: str


class ResolutionResult(_Strict):
    status: Resolution
    status_reason: str
    urgency: Level
    urgency_reason: str
    escalation_required: Escalation
    escalation_reason: str


class EvidenceItem(_Strict):
    turn: str = Field(pattern=r"^t\d+$")
    quote: str
    supports: str


class RootCause(_Strict):
    likely_cause: str
    observed_facts: list[str]
    assumptions: list[str]
    missing_information: list[str]


class RiskDetail(_Strict):
    level: Level
    reasons: list[str]


class RiskResult(_Strict):
    escalation: RiskDetail
    repeat_contact: RiskDetail


class ActionResult(_Strict):
    next_best_action: str
    team: str
    priority: Priority
    verify_before_closing: list[str]
    completion_criteria: str


class KnowledgeGap(_Strict):
    kind: GapKind
    statement: str
    attributed_to: str
    verification: str


class Confidence(_Strict):
    level: ConfidenceLevel
    reason: str


class Analysis(_Strict):
    id: str
    language: LanguageResult
    intent: IntentResult
    sentiment: SentimentResult
    resolution: ResolutionResult
    summary: str
    evidence: list[EvidenceItem]
    root_cause: RootCause
    risk: RiskResult
    action: ActionResult
    knowledge_gaps: list[KnowledgeGap]
    confidence: Confidence
    flags: list[str]

    @property
    def overall_risk(self) -> str:
        a, b = self.risk.escalation.level, self.risk.repeat_contact.level
        return a if LEVEL_ORDER[a] >= LEVEL_ORDER[b] else b
