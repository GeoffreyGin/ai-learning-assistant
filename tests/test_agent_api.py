"""Agent chat tests: the spec §27 end-to-end learning loop with a scripted LLM."""

import re

from fastapi.testclient import TestClient

from app.agent.controller import PrerequisiteSuggestions, TargetConcept
from app.knowledge.extractor import ExtractedConcept, ExtractionResult
from app.learning.assessment import GeneratedAssessment

_NO_CONCEPT = TargetConcept(concept_name="")


def _quant_finance_extraction(messages):
    return ExtractionResult(
        concepts=[
            ExtractedConcept(name="Brownian Motion", description="Random continuous movement."),
            ExtractedConcept(name="Black-Scholes", description="An option pricing model."),
        ],
        relationships=[],
    )


def _question_for(messages):
    text = messages[-1].content
    name = re.search(r"Concept: (.+)", text).group(1).strip()
    return GeneratedAssessment(
        concept=name,
        difficulty=1,
        question_type="true_false",
        question=f"Is {name} an important concept?",
        expected_answer="true",
        solution_outline="",
    )


def _upload_quant_material(llm_client: TestClient, fake_llm) -> None:
    fake_llm.structured[ExtractionResult] = _quant_finance_extraction
    upload = llm_client.post(
        "/documents/upload",
        files={"file": ("quant.md", b"# Brownian Motion\n# Black-Scholes", "text/markdown")},
    )
    assert upload.status_code == 201, upload.text
    assert upload.json()["new_concept_count"] == 2


def test_full_learning_loop_end_to_end(llm_client: TestClient, fake_llm) -> None:
    fake_llm.structured[GeneratedAssessment] = _question_for
    fake_llm.structured[PrerequisiteSuggestions] = lambda messages: PrerequisiteSuggestions(
        prerequisites=["Ito's Lemma", "Calculus"]
    )
    fake_llm.text_replies = ["Ito's Lemma extends the chain rule to stochastic processes [1]."]
    _upload_quant_material(llm_client, fake_llm)

    # 1. User chooses a target concept.
    learn = llm_client.post("/agent/chat", json={"message": "help me learn Black-Scholes"})
    assert learn.status_code == 200, learn.text
    payload = learn.json()
    reply = payload["reply"]
    assert "Goal: Black-Scholes" in reply
    assert "Ito's Lemma" in reply  # LLM-suggested missing prerequisite
    assert "no evidence" in reply
    assert "Question" in reply
    assert payload["pending"] and payload["pending"]["attempt_id"]
    tools = {action["tool"] for action in payload["actions"]}
    assert {"suggest_prerequisites", "detect_gaps", "explain", "generate_assessment"} <= tools

    # 2. User answers the question; mastery updates and the next step is recommended.
    answer = llm_client.post("/agent/chat", json={"message": "yes"})
    assert answer.status_code == 200
    reply = answer.json()["reply"]
    assert "Correct" in reply
    assert "Mastery for Ito's Lemma" in reply
    assert "no evidence →" in reply
    answer_tools = {action["tool"] for action in answer.json()["actions"]}
    assert "record_assessment" in answer_tools

    # 3. Mastery persisted: gaps endpoint reflects the new evidence.
    concepts = llm_client.get("/concepts").json()
    black_scholes = next(c for c in concepts if c["name"] == "Black-Scholes")
    gaps = llm_client.get(f"/learning/gaps/{black_scholes['id']}").json()
    statuses = {entry["concept"]["name"]: entry["status"] for entry in gaps["prerequisites"]}
    assert statuses["Ito's Lemma"] == "UNKNOWN"
    assert statuses["Calculus"] == "UNKNOWN"
    ito_id = next(c["id"] for c in concepts if c["name"] == "Ito's Lemma")
    ito_detail = llm_client.get(f"/concepts/{ito_id}").json()
    assert ito_detail["source_chunks"] == []  # suggested by the agent, not grounded in material

    # 4. Recommendation endpoint works from the graph.
    recommendation = llm_client.get("/learning/recommendation").json()["topics"]
    assert recommendation


def test_test_me_flow_picks_concept_and_evaluates(llm_client: TestClient, fake_llm) -> None:
    fake_llm.structured[GeneratedAssessment] = _question_for
    _upload_quant_material(llm_client, fake_llm)

    test = llm_client.post("/agent/chat", json={"message": "test me on Brownian Motion"})
    assert test.status_code == 200
    payload = test.json()
    assert "Brownian Motion" in payload["reply"]
    assert payload["pending"]["concept_name"] == "Brownian Motion"

    answer = llm_client.post("/agent/chat", json={"message": "false"})
    assert answer.status_code == 200
    assert "Not quite" in answer.json()["reply"]

    concepts = llm_client.get("/concepts").json()
    brownian = next(c for c in concepts if c["name"] == "Brownian Motion")
    mastery = llm_client.get("/graph").json()["nodes"]
    brownian_node = next(node for node in mastery if node["id"] == brownian["id"])
    assert brownian_node["mastery"] == 0.0  # incorrect first answer moves nothing from zero


def test_test_me_without_concept_picks_weakest(llm_client: TestClient, fake_llm) -> None:
    fake_llm.structured[GeneratedAssessment] = _question_for
    fake_llm.structured[TargetConcept] = _NO_CONCEPT
    _upload_quant_material(llm_client, fake_llm)
    test = llm_client.post("/agent/chat", json={"message": "test me"})
    assert test.status_code == 200
    assert test.json()["pending"]


def test_recommend_intent_returns_ranked_topics(llm_client: TestClient, fake_llm) -> None:
    fake_llm.structured[TargetConcept] = _NO_CONCEPT
    _upload_quant_material(llm_client, fake_llm)
    response = llm_client.post("/agent/chat", json={"message": "what should I study next?"})
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "Recommended next topics:" in reply
    assert "Brownian Motion" in reply


def test_fallback_chat_uses_llm(llm_client: TestClient, fake_llm) -> None:
    fake_llm.text_replies = ["Try 'help me learn X' to set a goal."]
    response = llm_client.post("/agent/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json()["reply"] == "Try 'help me learn X' to set a goal."
    assert response.json()["pending"] is None


def test_learn_flow_without_llm_stays_deterministic(client: TestClient) -> None:
    created = client.post("/concepts", json={"name": "Calculus", "description": "About Calculus."})
    assert created.status_code == 201

    learn = client.post("/agent/chat", json={"message": "help me learn Calculus"})
    assert learn.status_code == 200
    payload = learn.json()
    assert "Goal: Calculus" in payload["reply"]
    assert "(no prerequisites recorded)" in payload["reply"]
    assert payload["pending"]

    answer = client.post("/agent/chat", json={"message": "calculus"})
    assert answer.status_code == 200
    assert "Mastery for Calculus" in answer.json()["reply"]


def test_chat_asks_for_concept_when_message_has_none(client: TestClient) -> None:
    response = client.post("/agent/chat", json={"message": "help me learn"})
    assert response.status_code == 200
    assert "Which concept" in response.json()["reply"]


def test_unknown_intent_with_pending_question_evaluates_it(client: TestClient) -> None:
    created = client.post("/concepts", json={"name": "Calculus", "description": "About Calculus."})
    concept_id = created.json()["id"]
    client.post("/assessment/generate", json={"concept_id": concept_id})
    answer = client.post("/agent/chat", json={"message": "calculus is about rates of change"})
    assert answer.status_code == 200
    assert "Correct" in answer.json()["reply"]
    assert answer.json()["pending"] is None
    # The attempt is now answered, so a second chat message no longer evaluates it.
    second = client.post("/agent/chat", json={"message": "hello again"})
    assert second.json()["pending"] is None
    assert "record_assessment" not in {action["tool"] for action in second.json()["actions"]}
