async def test_list_conversations(client):
    r = await client.get("/api/conversations")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 10
    assert {"turns", "overall_risk", "summary", "evidence"} <= set(data[0])


async def test_get_conversation_and_404(client):
    ok = await client.get("/api/conversations/CALL-006")
    assert ok.status_code == 200
    assert ok.json()["intent"]["value"] == "Complaint"
    assert (await client.get("/api/conversations/CALL-999")).status_code == 404


async def test_filters_endpoint(client):
    d = (await client.get("/api/filters")).json()
    assert set(d) == {"language", "sentiment", "intent", "resolution", "risk"}
    assert "Mixed" in d["language"]


async def test_filter_by_resolution_unknown(client):
    data = (await client.get("/api/conversations?resolution=Unknown")).json()
    assert [c["id"] for c in data] == ["CALL-008"]
    res = (await client.get("/api/analytics/resolution?resolution=Unknown")).json()
    assert res["shown"] == 1 and res["total"] == 10 and res["resolution_rate"] == 0.0


async def test_combined_filters(client):
    data = (await client.get("/api/conversations?language=Mixed&risk=High")).json()
    assert {c["id"] for c in data} == {"CALL-005", "CALL-006", "CALL-009"}
