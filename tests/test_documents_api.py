from fastapi.testclient import TestClient


def test_directory_lists_live_ids_for_named_choices(client: TestClient) -> None:
    assert client.get("/directory").json() == {"documents": [], "concepts": []}
    for heading in ("Probability", "Calculus"):
        upload = client.post("/documents/upload", files={"file": ("notes.md", f"# {heading}")})
        upload.raise_for_status()

    directory = client.get("/directory").json()
    assert [doc["title"] for doc in directory["documents"]] == ["notes", "notes"]
    assert len({doc["id"] for doc in directory["documents"]}) == 2
    for doc in directory["documents"]:
        summary = client.post(f"/documents/{doc['id']}/knowledge-summary")
        assert summary.json()["document_id"] == doc["id"]
    assert [concept["name"] for concept in directory["concepts"]] == ["Calculus", "Probability"]
    for concept in directory["concepts"]:
        assert client.get(f"/concepts/{concept['id']}").json()["name"] == concept["name"]


def test_upload_text_creates_traceable_document_and_concepts(client: TestClient) -> None:
    source = b"# Brownian Motion\nBrownian Motion is used with Ito's Lemma in quantitative finance."
    response = client.post(
        "/documents/upload", files={"file": ("finance.md", source, "text/markdown")}
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["chunk_count"] == 1
    assert payload["new_concept_count"] >= 2

    document = client.get(f"/documents/{payload['document']['id']}")
    assert document.status_code == 200
    assert document.json()["chunks"][0]["text"] == source.decode()

    concepts = client.get("/concepts").json()
    names = {concept["name"] for concept in concepts}
    assert "Brownian Motion" in names
    brownian_id = next(
        concept["id"] for concept in concepts if concept["name"] == "Brownian Motion"
    )
    concept = client.get(f"/concepts/{brownian_id}")
    assert concept.status_code == 200
    assert concept.json()["source_chunks"][0]["document_id"] == payload["document"]["id"]


def test_upload_rejects_unsupported_file_type(client: TestClient) -> None:
    response = client.post(
        "/documents/upload", files={"file": ("notes.docx", b"x", "application/octet-stream")}
    )
    assert response.status_code == 422


def test_knowledge_summary_is_grounded_in_document_chunks(client: TestClient) -> None:
    source = (
        b"# Brownian Motion\n"
        b"Brownian Motion models random movement and is a central stochastic process. "
        b"# Ito's Lemma\n"
        b"Ito's Lemma extends the chain rule for stochastic processes."
    )
    upload = client.post("/documents/upload", files={"file": ("notes.md", source, "text/markdown")})
    document_id = upload.json()["document"]["id"]

    response = client.post(f"/documents/{document_id}/knowledge-summary")
    assert response.status_code == 200
    summary = response.json()
    assert "Brownian Motion" in summary["key_concepts"]
    assert "Ito's Lemma" in summary["key_concepts"]
    assert summary["claims"]

    document = client.get(f"/documents/{document_id}").json()
    chunk_ids = {chunk["id"] for chunk in document["chunks"]}
    assert all(claim["source_chunk_id"] in chunk_ids for claim in summary["claims"])
