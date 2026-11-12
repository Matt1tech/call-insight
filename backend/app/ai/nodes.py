"""Nodes of the analysis graph.

Every analysis node is the same shape: ``prompt | model.with_structured_output(Slice)`` in
live mode, or a lookup of the reviewed analysis in replay mode. Pure helpers
(``detect_language``, ``verify_evidence``) are exposed for reuse and testing.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.ai.llm_client import get_llm_settings
from app.ai.prompts.prompts import build_prompt
from app.ai.slices import EvidenceResult, KnowledgeGapResult, SummaryResult
from app.ai.state import AnalysisState
from app.schemas.analysis import (
    ActionResult,
    Analysis,
    EvidenceItem,
    IntentResult,
    LanguageResult,
    ResolutionResult,
    RiskResult,
    RootCause,
    SentimentResult,
)

# --------------------------------------------------------------------------- language

MALAY_MARKERS = frozenset(
    """saya puan tuan boleh adakah apakah apa yang dan untuk dengan tetapi kepada kami kerana
    sudah belum masih dah tak tiada ya ada ini itu hari bulan semalam sekarang esok lepas
    pagi baki bantuan barang pembelian akaun laporan kredit mesej skrin semak resit potongan
    pembayaran pembetulan arahan susulan rujuk rujukan sahkan mengesahkan mencuba cuba
    tolong perlukan hubungi minta seseorang terima kasih gembira betul semua satu dua kali
    nampak kata juruwang catatan lama bertanda selesai pasti maksudkan mungkin ingat nombor
    tahu rasa malu tanya telefon minggu sampai rumah makanan habis hampir dapur kosong faham
    kiraan cuma puas hati cara aduan dikendalikan gagal beli diluluskan jumlah pihak
    terangkan dihadapi biasanya menunjukkan tunggu semakan perkembangan terdahulu dipaparkan
    langkah seterusnya kepastian keadaan pasukan mengendalikan tindakan segera pergi
    membeli membuat berjaya lagi sama masa buat ingin tentang membantu sehingga""".split()
)

ENGLISH_MARKERS = frozenset(
    """the is are was were i my me you your to and of that this it but can will please for
    with what how did any there not no yes thank have has had in on at be been if do does so
    now still balance payment complaint called nobody someone supervisor cashier groceries
    purchase amount correct help assistance programme approved items item list which where
    when would like received message about from after before because need want heard true
    written available verify travel wait tomorrow tonight today deducted returned showing
    treated front customers other reported refer team follow update promised""".split()
)

# A language counts as present when at least this many of its marker words occur.
MIN_MARKERS = 3


def detect_language(turns: list[dict[str, Any]]) -> LanguageResult:
    """Heuristic language detector based on Malay and English marker words."""
    words = re.findall(r"[a-zA-Z']+", " ".join(t["text"] for t in turns).lower())
    malay = sum(w in MALAY_MARKERS for w in words)
    english = sum(w in ENGLISH_MARKERS for w in words)
    basis = (
        f"Heuristic: {malay} Bahasa Malaysia and {english} English marker words across all turns."
    )
    if malay >= MIN_MARKERS and english >= MIN_MARKERS:
        value = "Mixed"
    elif malay + english == 0 or malay == english:
        value = "Unknown"
    else:
        value = "Bahasa Malaysia" if malay > english else "English"
    return LanguageResult(value=value, basis=basis)


# --------------------------------------------------------------------------- evidence


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_evidence(
    turns: list[dict[str, Any]], evidence: list[EvidenceItem]
) -> tuple[list[EvidenceItem], list[str]]:
    """Keep evidence whose quote is a verbatim substring of its cited turn.

    Returns the kept items and one error message per dropped item.
    """
    by_turn = {t["turn"]: _normalise(t["text"]) for t in turns}
    kept: list[EvidenceItem] = []
    errors: list[str] = []
    for item in evidence:
        if item.turn not in by_turn:
            errors.append(f"evidence dropped: unknown turn {item.turn}")
        elif _normalise(item.quote) not in by_turn[item.turn]:
            errors.append(
                f"evidence dropped: quote not found verbatim in {item.turn}: {item.quote!r}"
            )
        else:
            kept.append(item)
    return kept, errors


# --------------------------------------------------------------------------- node specs


@dataclass(frozen=True)
class NodeSpec:
    name: str
    state_key: str
    slice_model: type[BaseModel]
    context_keys: tuple[str, ...]
    from_reviewed: Callable[[dict[str, Any]], dict[str, Any]]


NODE_SPECS: tuple[NodeSpec, ...] = (
    NodeSpec("classify_language", "language", LanguageResult, (), lambda a: a["language"]),
    NodeSpec("classify_intent", "intent", IntentResult, ("language",), lambda a: a["intent"]),
    NodeSpec(
        "analyse_sentiment",
        "sentiment",
        SentimentResult,
        ("language", "intent"),
        lambda a: a["sentiment"],
    ),
    NodeSpec(
        "assess_resolution",
        "resolution",
        ResolutionResult,
        ("intent", "sentiment"),
        lambda a: a["resolution"],
    ),
    NodeSpec(
        "extract_evidence",
        "evidence",
        EvidenceResult,
        ("intent", "sentiment", "resolution"),
        lambda a: {"evidence": a["evidence"]},
    ),
    NodeSpec(
        "analyse_root_cause",
        "root_cause",
        RootCause,
        ("intent", "resolution", "evidence"),
        lambda a: a["root_cause"],
    ),
    NodeSpec(
        "predict_risks",
        "risk",
        RiskResult,
        ("sentiment", "resolution", "root_cause"),
        lambda a: a["risk"],
    ),
    NodeSpec(
        "recommend_action",
        "action",
        ActionResult,
        ("resolution", "root_cause", "risk"),
        lambda a: a["action"],
    ),
    NodeSpec(
        "detect_knowledge_gaps",
        "knowledge",
        KnowledgeGapResult,
        ("resolution", "root_cause", "evidence"),
        lambda a: {"gaps": a["knowledge_gaps"]},
    ),
    NodeSpec(
        "summarise_and_score",
        "summary_score",
        SummaryResult,
        (
            "language",
            "intent",
            "sentiment",
            "resolution",
            "root_cause",
            "risk",
            "action",
            "knowledge",
        ),
        lambda a: {"summary": a["summary"], "confidence": a["confidence"], "flags": a["flags"]},
    ),
)

# Which node produces each field of the final Analysis (used to pick a node to retry).
FIELD_TO_NODE = {
    "language": "classify_language",
    "intent": "classify_intent",
    "sentiment": "analyse_sentiment",
    "resolution": "assess_resolution",
    "evidence": "extract_evidence",
    "root_cause": "analyse_root_cause",
    "risk": "predict_risks",
    "action": "recommend_action",
    "knowledge_gaps": "detect_knowledge_gaps",
    "summary": "summarise_and_score",
    "confidence": "summarise_and_score",
    "flags": "summarise_and_score",
}


def _context(state: AnalysisState, keys: tuple[str, ...]) -> str:
    parts = []
    for key in keys:
        value = state.get(key)
        if value is not None:
            parts.append(f"{key}: {value.model_dump_json()}")  # type: ignore[union-attr]
    return "\n".join(parts) or "(none)"


def prepare_transcript(state: AnalysisState) -> dict[str, Any]:
    """Normalise speaker turns and render the transcript text used in prompts."""
    turns = []
    for index, turn in enumerate(state["turns"], start=1):
        turns.append(
            {
                "turn": turn.get("turn") or f"t{index}",
                "speaker": turn.get("speaker", "Unknown"),
                "label": turn.get("label") or turn.get("speaker", "Unknown"),
                "text": str(turn["text"]).strip(),
            }
        )
    text = "\n".join(f"{t['turn']} [{t['speaker']}]: {t['text']}" for t in turns)
    return {"turns": turns, "transcript_text": text, "errors": [], "retries": 0}


def make_analysis_node(
    spec: NodeSpec,
    mode: str,
    model: Any | None,
    reviewed: dict[str, dict[str, Any]],
) -> Callable[[AnalysisState], dict[str, Any]]:
    """Create the graph node for one analysis step."""
    chain = None
    if mode == "live":
        if model is None:
            raise ValueError("live mode requires a chat model")
        structured = model.with_structured_output(
            spec.slice_model, method=get_llm_settings().cloudflare_structured_method
        )
        chain = build_prompt(spec.name) | structured

    def node(state: AnalysisState) -> dict[str, Any]:
        try:
            if mode == "replay":
                result = spec.slice_model.model_validate(
                    spec.from_reviewed(reviewed[state["conversation_id"]])
                )
            else:
                raw = chain.invoke(  # type: ignore[union-attr]
                    {
                        "conversation_id": state["conversation_id"],
                        "transcript": state["transcript_text"],
                        "context": _context(state, spec.context_keys),
                    }
                )
                result = (
                    raw
                    if isinstance(raw, spec.slice_model)
                    else spec.slice_model.model_validate(raw)
                )
        except KeyError:
            return {"errors": [f"{spec.name}: no reviewed analysis for this conversation"]}
        except (ValidationError, ValueError, TypeError) as exc:
            return {"errors": [f"{spec.name}: invalid output ({type(exc).__name__}: {exc})"]}
        except Exception as exc:  # noqa: BLE001 - provider/network errors must not crash the run
            return {"errors": [f"{spec.name}: model call failed ({type(exc).__name__}: {exc})"]}

        update: dict[str, Any] = {spec.state_key: result}
        if spec.name == "classify_language":
            update["errors"] = _language_cross_check(state, result)
        return update

    node.__name__ = spec.name
    return node


def _language_cross_check(state: AnalysisState, result: LanguageResult) -> list[str]:
    heuristic = detect_language(state["turns"])
    if heuristic.value != result.value:
        return [
            f"warning: language {result.value!r} differs from heuristic {heuristic.value!r} "
            f"({heuristic.basis})"
        ]
    return []


# --------------------------------------------------------------------------- validation


def validate_output(state: AnalysisState) -> dict[str, Any]:
    """Assemble the final Analysis, validate it, and check evidence quotes are verbatim."""
    errors: list[str] = []
    retry_node: str | None = None
    analysis: Analysis | None = None

    missing = [spec for spec in NODE_SPECS if state.get(spec.state_key) is None]
    if missing:
        retry_node = missing[0].name
        errors.append("missing outputs: " + ", ".join(s.name for s in missing))
    else:
        evidence, evidence_errors = verify_evidence(state["turns"], state["evidence"].evidence)  # type: ignore[union-attr]
        errors.extend(evidence_errors)
        if evidence_errors:
            retry_node = "extract_evidence"
        summary = state["summary_score"]
        try:
            analysis = Analysis(
                id=state["conversation_id"],
                language=state["language"],
                intent=state["intent"],
                sentiment=state["sentiment"],
                resolution=state["resolution"],
                summary=summary.summary,
                evidence=evidence,
                root_cause=state["root_cause"],
                risk=state["risk"],
                action=state["action"],
                knowledge_gaps=state["knowledge"].gaps,
                confidence=summary.confidence,
                flags=summary.flags,
            )
        except ValidationError as exc:
            for err in exc.errors():
                errors.append(f"validation: {'.'.join(map(str, err['loc']))}: {err['msg']}")
            first = str(exc.errors()[0]["loc"][0])
            retry_node = FIELD_TO_NODE.get(first)

    retries = state.get("retries", 0)
    can_retry = state.get("mode") == "live" and retries < 1 and retry_node is not None
    return {
        "analysis": analysis,
        "errors": errors,
        "retry_node": retry_node if can_retry else None,
        "retries": retries + 1 if can_retry else retries,
    }
