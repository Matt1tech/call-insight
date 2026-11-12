"""Loads and validates transcripts and reviewed analysis from local JSON."""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter

from app.core.config import get_settings
from app.schemas.analysis import Analysis
from app.schemas.conversation import Transcript


class AnalysisRepository:
    def __init__(self, data_dir: Path) -> None:
        transcripts = json.loads((data_dir / "transcripts" / "transcripts.json").read_text("utf-8"))
        analyses = json.loads((data_dir / "analysis" / "analysis.json").read_text("utf-8"))
        self.transcripts: dict[str, Transcript] = {
            t.id: t for t in TypeAdapter(list[Transcript]).validate_python(transcripts)
        }
        self.analyses: dict[str, Analysis] = {
            a.id: a for a in TypeAdapter(list[Analysis]).validate_python(analyses)
        }
        missing = set(self.transcripts) ^ set(self.analyses)
        if missing:
            raise ValueError(f"Transcript/analysis ids do not match: {sorted(missing)}")

    def ids(self) -> list[str]:
        return sorted(self.analyses)

    def get(self, call_id: str) -> tuple[Transcript, Analysis] | None:
        if call_id not in self.analyses:
            return None
        return self.transcripts[call_id], self.analyses[call_id]

    def all(self) -> list[tuple[Transcript, Analysis]]:
        return [(self.transcripts[i], self.analyses[i]) for i in self.ids()]


@lru_cache
def get_repository() -> AnalysisRepository:
    return AnalysisRepository(get_settings().data_dir)
