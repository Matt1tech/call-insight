"""Output wrappers for nodes whose result is a list or a combination of fields.

The slice models themselves (``LanguageResult`` etc.) live in ``app.schemas.analysis``;
these wrappers exist only because structured-output APIs need an object at the top level.
"""

from pydantic import BaseModel, ConfigDict

from app.schemas.analysis import Confidence, EvidenceItem, KnowledgeGap


class EvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: list[EvidenceItem]


class KnowledgeGapResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gaps: list[KnowledgeGap]


class SummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    confidence: Confidence
    flags: list[str]
