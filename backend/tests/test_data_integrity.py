"""Guards against hallucinated evidence: every quote must exist in its cited turn."""

from app.repositories.analysis_repository import get_repository


def test_all_ten_conversations_load():
    repo = get_repository()
    assert len(repo.ids()) == 10
    assert repo.ids()[0] == "CALL-001" and repo.ids()[-1] == "CALL-010"


def test_every_evidence_quote_is_verbatim_in_cited_turn():
    repo = get_repository()
    for transcript, analysis in repo.all():
        assert analysis.evidence, f"{analysis.id} has no evidence"
        for ev in analysis.evidence:
            text = transcript.turn_text(ev.turn)
            assert text is not None, f"{analysis.id}: turn {ev.turn} does not exist"
            assert ev.quote in text, f"{analysis.id} {ev.turn}: quote not found: {ev.quote!r}"


def test_unknown_is_never_counted_as_resolved():
    repo = get_repository()
    unknown = [a.id for _, a in repo.all() if a.resolution.status == "Unknown"]
    assert unknown == ["CALL-008"]
