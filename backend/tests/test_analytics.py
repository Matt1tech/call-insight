def _counts(items):
    return {i["label"]: i["count"] for i in items}


async def test_overview_totals(client):
    d = (await client.get("/api/analytics/overview")).json()
    assert d["total"] == 10 and d["shown"] == 10
    assert _counts(d["language"]) == {"English": 3, "Bahasa Malaysia": 3, "Mixed": 4}
    assert _counts(d["intent"]) == {"Programme Enquiry": 3, "Technical Support": 5, "Complaint": 2}
    assert _counts(d["sentiment"]) == {"Positive": 2, "Neutral": 4, "Negative": 4}
    assert sum(_counts(d["emotion"]).values()) == 10
    assert len(d["calls"]) == 10


async def test_resolution_rate_keeps_unknown_separate(client):
    d = (await client.get("/api/analytics/resolution")).json()
    assert (d["resolved"], d["unresolved"], d["unknown"]) == (3, 6, 1)
    assert d["resolution_rate"] == 30.0
    assert d["formula"] == "3 / 10"
    assert d["by_status"]["Unknown"] == ["CALL-008"]
    assert d["matrix"]["cells"]["Resolved|Positive"] == ["CALL-001", "CALL-003"]


async def test_risks(client):
    d = (await client.get("/api/analytics/risks")).json()
    assert d["escalation_cases"] == 6
    assert d["high_risk"] == 4
    assert d["cases"][0]["overall_risk"] == "High"
    assert {c["id"] for c in d["cases"] if c["overall_risk"] == "High"} == {
        "CALL-002",
        "CALL-005",
        "CALL-006",
        "CALL-009",
    }


async def test_knowledge_gaps(client):
    d = (await client.get("/api/analytics/knowledge-gaps")).json()
    statements = [g["statement"] for g in d["gaps"] if g["call_id"] == "CALL-007"]
    assert any("twelve months" in s for s in statements)
    assert any(f["call_id"] == "CALL-010" for f in d["flags"])
    assert d["programme_info_not_supplied"]


async def test_injection_in_call_010_is_ignored(client):
    d = (await client.get("/api/conversations/CALL-010")).json()
    assert d["resolution"]["status"] == "Unresolved"
    assert d["sentiment"]["sentiment"] == "Neutral"
