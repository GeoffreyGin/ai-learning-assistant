"""Learning API tests (spec §23, §26): gaps, recommendation, assessment generate/submit."""

from fastapi.testclient import TestClient


def _create_concept(client: TestClient, name: str, description: str = "") -> int:
    response = client.post("/concepts", json={"name": name, "description": description})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _link(client: TestClient, source: str, target: str) -> None:
    response = client.post(
        "/relationships",
        json={
            "source": source,
            "target": target,
            "relation_type": "PREREQUISITE_OF",
            "confidence": 0.9,
        },
    )
    assert response.status_code == 201, response.text


def test_gaps_endpoint_reports_unknown_prerequisites(client: TestClient) -> None:
    calculus_id = _create_concept(client, "Calculus")
    black_scholes_id = _create_concept(client, "Black-Scholes")
    _link(client, "Calculus", "Black-Scholes")

    response = client.get(f"/learning/gaps/{black_scholes_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["target"]["name"] == "Black-Scholes"
    assert [entry["concept"]["name"] for entry in payload["prerequisites"]] == ["Calculus"]
    assert payload["gaps"][0]["status"] == "UNKNOWN"
    assert payload["gaps"][0]["mastery"] is None
    assert calculus_id == payload["prerequisites"][0]["concept"]["id"]


def test_gaps_endpoint_404_for_missing_concept(client: TestClient) -> None:
    assert client.get("/learning/gaps/999").status_code == 404


def test_prerequisites_endpoint(client: TestClient) -> None:
    _create_concept(client, "Calculus")
    _create_concept(client, "Brownian Motion")
    black_scholes_id = _create_concept(client, "Black-Scholes")
    _link(client, "Calculus", "Brownian Motion")
    _link(client, "Brownian Motion", "Black-Scholes")

    response = client.get(f"/concepts/{black_scholes_id}/prerequisites")
    assert response.status_code == 200
    payload = response.json()
    assert [(item["concept"]["name"], item["distance"]) for item in payload] == [
        ("Brownian Motion", 1),
        ("Calculus", 2),
    ]


def test_generate_and_submit_full_loop(client: TestClient) -> None:
    concept_id = _create_concept(
        client,
        "Brownian Motion",
        description="A stochastic process models random movement over time.",
    )
    generated = client.post("/assessment/generate", json={"concept_id": concept_id})
    assert generated.status_code == 200, generated.text
    attempt_id = generated.json()["attempt_id"]
    assert generated.json()["question"]

    submitted = client.post(
        "/assessment/submit",
        json={
            "attempt_id": attempt_id,
            "user_answer": "a stochastic process models random movement",
        },
    )
    assert submitted.status_code == 200, submitted.text
    payload = submitted.json()
    assert payload["mastery_before"] is None
    assert payload["mastery_after"] > 0
    assert payload["evidence_count"] == 1

    gaps = client.get(f"/learning/gaps/{concept_id}").json()
    assert gaps["gaps"] == []  # no prerequisites recorded, so no gaps


def test_submit_unknown_attempt_is_rejected(client: TestClient) -> None:
    response = client.post("/assessment/submit", json={"attempt_id": 999, "user_answer": "x"})
    assert response.status_code == 422


def test_submit_twice_is_rejected(client: TestClient) -> None:
    concept_id = _create_concept(client, "Calculus")
    attempt_id = client.post("/assessment/generate", json={"concept_id": concept_id}).json()[
        "attempt_id"
    ]
    assert (
        client.post(
            "/assessment/submit", json={"attempt_id": attempt_id, "user_answer": "x"}
        ).status_code
        == 200
    )
    second = client.post("/assessment/submit", json={"attempt_id": attempt_id, "user_answer": "y"})
    assert second.status_code == 422


def test_recommendation_ranks_concepts_by_evidence(client: TestClient) -> None:
    tested_id = _create_concept(client, "Tested", description="tested concept with evidence")
    attempt_id = client.post("/assessment/generate", json={"concept_id": tested_id}).json()[
        "attempt_id"
    ]
    client.post(
        "/assessment/submit", json={"attempt_id": attempt_id, "user_answer": "tested concept"}
    )
    _create_concept(client, "Untested")

    response = client.get("/learning/recommendation")
    assert response.status_code == 200
    topics = response.json()["topics"]
    assert [topic["concept"]["name"] for topic in topics] == ["Untested", "Tested"]


def test_recommendation_for_target_returns_gaps(client: TestClient) -> None:
    _create_concept(client, "Calculus")
    target_id = _create_concept(client, "Black-Scholes")
    _link(client, "Calculus", "Black-Scholes")

    response = client.get(f"/learning/recommendation?concept_id={target_id}")
    assert response.status_code == 200
    topics = response.json()["topics"]
    assert topics[0]["concept"]["name"] == "Calculus"
    assert topics[0]["status"] == "UNKNOWN"


def test_graph_endpoint_includes_mastery(client: TestClient) -> None:
    concept_id = _create_concept(client, "Calculus")
    attempt_id = client.post("/assessment/generate", json={"concept_id": concept_id}).json()[
        "attempt_id"
    ]
    client.post("/assessment/submit", json={"attempt_id": attempt_id, "user_answer": "Calculus"})

    payload = client.get("/graph").json()
    node = next(node for node in payload["nodes"] if node["name"] == "Calculus")
    assert node["mastery"] is not None and node["mastery"] > 0


def test_relationship_deduplicates_and_validates(client: TestClient) -> None:
    _create_concept(client, "A")
    _create_concept(client, "B")
    first = client.post(
        "/relationships",
        json={"source": "A", "target": "B", "relation_type": "RELATED_TO", "confidence": 0.5},
    )
    assert first.status_code == 201
    second = client.post(
        "/relationships",
        json={"source": "A", "target": "B", "relation_type": "RELATED_TO", "confidence": 0.9},
    )
    assert second.status_code == 201
    assert second.json()["created"] is False
    assert second.json()["confidence"] == 0.9

    invalid = client.post(
        "/relationships",
        json={"source": "A", "target": "B", "relation_type": "FRIENDS_WITH", "confidence": 0.5},
    )
    assert invalid.status_code == 422
