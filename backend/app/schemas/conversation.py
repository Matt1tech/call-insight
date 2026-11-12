"""Schemas for source call transcripts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn: str = Field(pattern=r"^t\d+$")
    speaker: Literal["Agent", "Beneficiary"]
    label: str  # original speaker label, e.g. "Ejen" / "Penerima"
    text: str


class Transcript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    turns: list[Turn]

    def turn_text(self, turn_id: str) -> str | None:
        for t in self.turns:
            if t.turn == turn_id:
                return t.text
        return None
