"""Single source of truth for every dashboard metric.

All figures are derived from the validated analysis records, and every endpoint
accepts the same five optional filters so numbers stay consistent across views.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, get_args

from app.repositories.analysis_repository import AnalysisRepository
from app.schemas.analysis import (
    LEVEL_ORDER,
    Analysis,
    Intent,
    Language,
    Resolution,
    Sentiment,
)
from app.schemas.conversation import Transcript

RESOLUTION_ROWS = ["Resolved", "Unresolved", "Unknown"]
SENTIMENT_COLS = ["Positive", "Neutral", "Negative", "Unknown"]


@dataclass(frozen=True)
class Filters:
    language: str | None = None
    sentiment: str | None = None
    intent: str | None = None
    resolution: str | None = None
    risk: str | None = None


def allowed_filters() -> dict[str, list[str]]:
    return {
        "language": list(get_args(Language)),
        "sentiment": list(get_args(Sentiment)),
        "intent": list(get_args(Intent)),
        "resolution": list(get_args(Resolution)),
        "risk": ["High", "Medium", "Low", "Unknown"],
    }


def _distribution(values: list[str]) -> list[dict[str, Any]]:
    counts = Counter(values)
    return [
        {"label": label, "count": count}
        for label, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


class AnalyticsService:
    def __init__(self, repo: AnalysisRepository) -> None:
        self.repo = repo

    # ---- filtering -------------------------------------------------------
    def _select(self, f: Filters) -> list[tuple[Transcript, Analysis]]:
        out = []
        for transcript, a in self.repo.all():
            if f.language and a.language.value != f.language:
                continue
            if f.sentiment and a.sentiment.sentiment != f.sentiment:
                continue
            if f.intent and a.intent.value != f.intent:
                continue
            if f.resolution and a.resolution.status != f.resolution:
                continue
            if f.risk and a.overall_risk != f.risk:
                continue
            out.append((transcript, a))
        return out

    def _total(self) -> int:
        return len(self.repo.ids())

    # ---- conversations ---------------------------------------------------
    @staticmethod
    def merged_record(transcript: Transcript, a: Analysis) -> dict[str, Any]:
        record = a.model_dump()
        record["turns"] = [t.model_dump() for t in transcript.turns]
        record["overall_risk"] = a.overall_risk
        return record

    def conversations(self, f: Filters) -> list[dict[str, Any]]:
        return [self.merged_record(t, a) for t, a in self._select(f)]

    def conversation(self, call_id: str) -> dict[str, Any] | None:
        found = self.repo.get(call_id)
        return self.merged_record(*found) if found else None

    # ---- overview --------------------------------------------------------
    def overview(self, f: Filters) -> dict[str, Any]:
        rows = [a for _, a in self._select(f)]
        return {
            "total": self._total(),
            "shown": len(rows),
            "sentiment": _distribution([a.sentiment.sentiment for a in rows]),
            "emotion": _distribution([a.sentiment.emotion for a in rows]),
            "intent": _distribution([a.intent.value for a in rows]),
            "language": _distribution([a.language.value for a in rows]),
            "calls": [
                {
                    "id": a.id,
                    "language": a.language.value,
                    "intent": a.intent.value,
                    "sentiment": a.sentiment.sentiment,
                    "emotion": a.sentiment.emotion,
                    "tone": a.sentiment.tone,
                    "resolution": a.resolution.status,
                    "urgency": a.resolution.urgency,
                    "overall_risk": a.overall_risk,
                    "escalation_required": a.resolution.escalation_required,
                    "summary": a.summary,
                }
                for a in rows
            ],
        }

    # ---- resolution ------------------------------------------------------
    def resolution(self, f: Filters) -> dict[str, Any]:
        rows = [a for _, a in self._select(f)]
        by_status: dict[str, list[str]] = {r: [] for r in RESOLUTION_ROWS}
        cells: dict[str, list[str]] = {
            f"{r}|{c}": [] for r in RESOLUTION_ROWS for c in SENTIMENT_COLS
        }
        for a in rows:
            by_status[a.resolution.status].append(a.id)
            cells[f"{a.resolution.status}|{a.sentiment.sentiment}"].append(a.id)
        shown = len(rows)
        resolved = len(by_status["Resolved"])
        return {
            "total": self._total(),
            "shown": shown,
            "resolved": resolved,
            "unresolved": len(by_status["Unresolved"]),
            "unknown": len(by_status["Unknown"]),
            # Resolution rate = Resolved / analysed conversations; Unknown stays in the denominator.
            "resolution_rate": round(resolved / shown * 100, 1) if shown else 0.0,
            "formula": f"{resolved} / {shown}",
            "by_status": by_status,
            "matrix": {"rows": RESOLUTION_ROWS, "cols": SENTIMENT_COLS, "cells": cells},
        }

    # ---- risks -----------------------------------------------------------
    def risks(self, f: Filters) -> dict[str, Any]:
        rows = [a for _, a in self._select(f)]
        cases = [
            {
                "id": a.id,
                "intent": a.intent.value,
                "urgency": a.resolution.urgency,
                "priority": a.action.priority,
                "escalation_required": a.resolution.escalation_required,
                "escalation_reason": a.resolution.escalation_reason,
                "escalation_level": a.risk.escalation.level,
                "escalation_reasons": a.risk.escalation.reasons,
                "repeat_level": a.risk.repeat_contact.level,
                "repeat_reasons": a.risk.repeat_contact.reasons,
                "overall_risk": a.overall_risk,
                "team": a.action.team,
                "next_best_action": a.action.next_best_action,
            }
            for a in rows
        ]
        cases.sort(key=lambda c: (-LEVEL_ORDER[c["overall_risk"]], c["id"]))
        return {
            "total": self._total(),
            "shown": len(rows),
            "escalation_cases": sum(a.resolution.escalation_required == "Yes" for a in rows),
            "high_risk": sum(a.overall_risk == "High" for a in rows),
            "escalation_risk": _distribution([a.risk.escalation.level for a in rows]),
            "repeat_contact_risk": _distribution([a.risk.repeat_contact.level for a in rows]),
            "cases": cases,
        }

    # ---- knowledge gaps --------------------------------------------------
    def knowledge_gaps(self, f: Filters) -> dict[str, Any]:
        rows = [a for _, a in self._select(f)]
        gaps = [{"call_id": a.id, **g.model_dump()} for a in rows for g in a.knowledge_gaps]
        missing: dict[str, list[str]] = defaultdict(list)
        for g in gaps:
            if g["kind"] == "missing_programme_info":
                missing[g["statement"]].append(g["call_id"])
        return {
            "shown": len(rows),
            "gaps": gaps,
            "by_kind": _distribution([g["kind"] for g in gaps]),
            "flags": [{"call_id": a.id, "flag": fl} for a in rows for fl in a.flags],
            "programme_info_not_supplied": [
                {"statement": s, "call_ids": ids} for s, ids in missing.items()
            ],
        }
