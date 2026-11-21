"""Agent controller: the learning loop (spec §14).

Deterministic routing decides what the user wants, then the controller runs small,
observable steps: find the target, retrieve the prerequisite graph, retrieve mastery
evidence, identify gaps, decide what to teach first, generate learning content, test
the user, update mastery, and recommend the next step. Every step is a logged tool call.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.logging import ActionLogger
from app.agent.prompts import (
    CHAT_SYSTEM_PROMPT,
    EXPLANATION_SYSTEM_PROMPT,
    PREREQUISITE_SUGGESTION_PROMPT,
    TARGET_EXTRACTION_PROMPT,
)
from app.agent.tools import ToolSet
from app.core.config import Settings
from app.db.models import Concept, PracticeGuide, TutorTurn
from app.learning.guidance import give_clue, pending_question, start_lecture
from app.learning.gap_detector import MASTERED, UNKNOWN, WEAK
from app.llm.provider import LLMError, LLMMessage, LLMProvider

RECOMMEND_INTENT = re.compile(
    r"\bwhat\s+(should|next|now|do)\b|\bnow what\b|\brecommend\b", re.IGNORECASE
)
LEARN_INTENT = re.compile(
    r"\b(learn|learning|study|studying|understand|master|teach me)\b", re.IGNORECASE
)
TEST_INTENT = re.compile(r"\b(test|testing|quiz|assess|examine)\b", re.IGNORECASE)
CONTINUE_INTENT = re.compile(r"^(continue|go on|next( question)?|more)[.!]?$", re.IGNORECASE)
HELP_INTENT = re.compile(
    r"\b(hint|clue|stuck|confused)\b|^(why\b|how (do|can|did|does)\b|"
    r"explain (this|that|step)\b|i (don't|don’t|do not) (know|understand))", re.IGNORECASE
)

_STATUS_SYMBOLS = {MASTERED: "✓", WEAK: "△", UNKNOWN: "✗"}


class TargetConcept(BaseModel):
    concept_name: str = Field(default="", max_length=255)


class PrerequisiteSuggestions(BaseModel):
    prerequisites: list[str] = Field(default_factory=list, max_length=8)


class AgentController:
    def __init__(self, session_factory, llm: LLMProvider | None, settings: Settings) -> None:
        self.session_factory = session_factory
        self.llm = llm
        self.settings = settings
        # In-memory link from a pending question to the user's overall goal concept.
        # Best-effort only: if lost (server restart), recommendations fall back to
        # the answered concept itself. Knowledge and mastery live in the database.
        self.goal_by_attempt: dict[int, int | None] = {}

    def history(self):
        with self.session_factory() as session:
            turns = session.scalars(select(TutorTurn).order_by(TutorTurn.id.desc()).limit(60)).all()
            return [{"message": t.message, **t.response} for t in reversed(turns)]

    def chat(self, message: str, *, document_id=None, concept_id=None, attempt_id=None,
             hint=False, step=None) -> dict:
        with self.session_factory() as session:
            logger = ActionLogger(self.settings.data_dir / "agent.log")
            tools = ToolSet(session, llm=self.llm, settings=self.settings, logger=logger)
            text = message.strip()
            if not text:
                raise ValueError("Enter a message.")
            attempt = (tools.repository.get_attempt(attempt_id) if attempt_id
                       else tools.repository.latest_pending_attempt())
            if attempt_id and (attempt is None or attempt.user_answer is not None):
                raise ValueError("This question is no longer open.")
            if document_id is not None or concept_id is not None:
                reply, pending = start_lecture(tools, document_id, concept_id)
            elif hint or (attempt and HELP_INTENT.search(text)):
                if attempt is None:
                    reply, pending = "Choose a lecture topic or start a question to get a clue.", None
                else:
                    reply, pending = give_clue(tools, attempt, text, step)
            elif attempt_id:
                reply, pending = self._handle_answer(text, tools, attempt)
            elif RECOMMEND_INTENT.search(text):
                reply, pending = self._handle_recommend(text, tools)
            elif LEARN_INTENT.search(text):
                reply, pending = self._handle_learn(text, tools)
            elif TEST_INTENT.search(text):
                reply, pending = self._handle_test(text, tools)
            elif CONTINUE_INTENT.match(text):
                reply, pending = self._handle_continue(tools)
            else:
                if attempt is not None:
                    reply, pending = self._handle_answer(text, tools, attempt)
                else:
                    reply, pending = self._handle_chat(text, tools)
            response = {"reply": reply, "actions": logger.entries, "pending": pending}
            session.add(TutorTurn(message=text, response=response))
            session.commit()
            return response

    # -- Intent handlers ------------------------------------------------------

    def _handle_learn(self, message: str, tools: ToolSet) -> tuple[str, dict | None]:
        concept = self._find_target(message, tools)
        if concept is None:
            return "Which concept would you like to learn? Try 'help me learn <concept>'.", None
        if not tools.graph.prerequisites(concept.id) and self.llm is not None:
            self._suggest_prerequisites(concept, tools)

        report = tools.gap_detector.detect(concept.id)
        tools.logger.log(
            "detect_gaps",
            f"target={concept.name!r} -> {len(report.prerequisites)} prerequisite(s), "
            f"{len(report.gaps)} gap(s)",
        )
        teach = report.gaps[0].concept if report.gaps else concept
        explanation = self._explain(teach, tools)
        assessment = tools.generate_assessment(teach.id)
        self.goal_by_attempt[assessment["attempt_id"]] = concept.id

        lines = [f"Goal: {concept.name}", "", "Prerequisite status:"]
        for entry in report.prerequisites:
            symbol = _STATUS_SYMBOLS[entry.status]
            mastery_text = f"{entry.mastery:.0%}" if entry.mastery is not None else "no evidence"
            lines.append(f"{symbol} {entry.concept.name} — {entry.status} ({mastery_text})")
        if not report.prerequisites:
            lines.append("(no prerequisites recorded)")
        if report.gaps:
            top = report.gaps[0]
            lines += [
                "",
                f"Recommendation: start with {top.concept.name} — {self._gap_reason(top.status)}.",
            ]
        lines += [
            "",
            explanation,
            "",
            "Question (answer in your next message):",
            assessment["question"],
        ]
        return "\n".join(lines), {
            "attempt_id": assessment["attempt_id"],
            "concept_id": teach.id,
            "concept_name": teach.name,
            "question": assessment["question"],
        }

    def _handle_test(self, message: str, tools: ToolSet) -> tuple[str, dict | None]:
        concept = self._find_target(message, tools)
        if concept is None:
            topics = tools.recommender.recommend(None, 1)
            if not topics:
                return "There are no concepts to test yet — upload some material first.", None
            concept = topics[0].concept
            tools.logger.log("pick_weakest_concept", f"chose {concept.name!r}")
        assessment = tools.generate_assessment(concept.id)
        self.goal_by_attempt[assessment["attempt_id"]] = None
        reply = (
            f"Here is a question on {concept.name} (difficulty {assessment['difficulty']}):\n\n"
            f"{assessment['question']}"
        )
        return reply, {
            "attempt_id": assessment["attempt_id"],
            "concept_id": concept.id,
            "concept_name": concept.name,
            "question": assessment["question"],
        }

    def _handle_recommend(self, message: str, tools: ToolSet) -> tuple[str, dict | None]:
        concept = self._find_target(message, tools)
        topics = tools.recommender.recommend(concept.id if concept else None)
        if not topics:
            return "Nothing to recommend yet — add material or set a goal first.", None
        lines = ["Recommended next topics:"]
        for index, topic in enumerate(topics, 1):
            mastery = f"{topic.mastery:.0%}" if topic.mastery is not None else "no evidence"
            lines.append(
                f"{index}. {topic.concept.name} — {topic.status} ({mastery}) — {topic.reason}"
            )
        return "\n".join(lines), None

    def _handle_answer(self, text: str, tools: ToolSet, attempt) -> tuple[str, dict | None]:
        concept = tools.repository.get_concept(attempt.concept_id)
        concept_name = concept.name if concept else f"concept {attempt.concept_id}"
        before = tools.mastery.get_estimate(attempt.concept_id)
        result = tools.record_assessment(attempt.id, text)
        goal_id = self.goal_by_attempt.pop(attempt.id, None)

        lines = [
            ("✓ Correct" if result["correct"] else "✗ Not quite")
            + f" (score {result['score']:.2f})"
        ]
        if result["reasoning"]:
            lines.append(result["reasoning"])
        for mistake in result["identified_mistakes"]:
            lines.append(f"- {mistake}")
        before_text = f"{before:.0%}" if before is not None else "no evidence"
        lines += [
            "",
            f"Mastery for {concept_name}: {before_text} → {result['estimated_mastery']:.0%}",
            "",
            "Next:",
        ]
        if goal_id is not None:
            topics = tools.recommender.recommend(goal_id, 1)
            if topics and topics[0].status != MASTERED:
                lines.append(
                    f"Still working toward your goal — next up: {topics[0].concept.name}. "
                    "Say 'continue' for the next question."
                )
            else:
                lines.append(
                    "Goal prerequisites look done — ask me to test you on the goal itself."
                )
        else:
            topics = tools.recommender.recommend(None, 1)
            if topics:
                lines.append(f"Suggested next: {topics[0].concept.name} — {topics[0].reason}")
        return "\n".join(lines), None

    def _handle_continue(self, tools: ToolSet) -> tuple[str, dict | None]:
        pending_attempt = tools.repository.latest_pending_attempt()
        if pending_attempt is not None:
            concept = tools.repository.get_concept(pending_attempt.concept_id)
            name = concept.name if concept else "?"
            return (
                f"There is an open question on {name} — answer it first:\n\n"
                f"{pending_attempt.question}",
                pending_question(pending_attempt, tools.session.get(PracticeGuide, pending_attempt.id)),
            )
        topics = tools.recommender.recommend(None, 1)
        if not topics:
            return "Nothing to continue with — upload material or set a goal first.", None
        concept = topics[0].concept
        assessment = tools.generate_assessment(concept.id)
        self.goal_by_attempt[assessment["attempt_id"]] = None
        return (
            f"Continuing with {concept.name} — {topics[0].reason}\n\n{assessment['question']}",
            {
                "attempt_id": assessment["attempt_id"],
                "concept_id": concept.id,
                "concept_name": concept.name,
                "question": assessment["question"],
            },
        )

    def _handle_chat(self, text: str, tools: ToolSet) -> tuple[str, dict | None]:
        if self.llm is not None:
            concepts = tools.repository.list_concepts()[:10]
            context = (
                "\n".join(
                    f"- {concept.name}: mastery "
                    f"{self._format_mastery(tools.mastery.get_estimate(concept.id))}"
                    for concept in concepts
                )
                or "(no concepts yet)"
            )
            try:
                history = tools.session.scalars(
                    select(TutorTurn).order_by(TutorTurn.id.desc()).limit(4)
                ).all()
                recent = [
                    message for turn in reversed(history) for message in (
                        LLMMessage(role="user", content=turn.message[:1500]),
                        LLMMessage(role="assistant", content=turn.response["reply"][:1500]),
                    )
                ]
                reply = self.llm.generate(
                    [
                        LLMMessage(role="system", content=CHAT_SYSTEM_PROMPT),
                        *recent,
                        LLMMessage(
                            role="user", content=f"Known concepts:\n{context}\n\nUser: {text}"
                        ),
                    ],
                    max_tokens=500,
                    temperature=0.4,
                )
                tools.logger.log("chat", f"llm response ({len(reply)} chars)")
                return reply, None
            except LLMError as error:
                tools.logger.log("chat", f"llm failed, falling back: {error}")
        return (
            "I am your knowledge-and-learning agent. Try:\n"
            "- 'help me learn <concept>'\n"
            "- 'test me on <concept>'\n"
            "- 'what should I study next?'"
        ), None

    # -- Shared helpers --------------------------------------------------------

    def _find_target(self, message: str, tools: ToolSet) -> Concept | None:
        """Longest known concept name mentioned in the message; otherwise ask the LLM."""
        best: Concept | None = None
        for concept in tools.repository.list_concepts():
            if concept.name.casefold() in message.casefold():
                if best is None or len(concept.name) > len(best.name):
                    best = concept
        if best is not None:
            return best
        if self.llm is not None:
            try:
                extracted = self.llm.structured_generate(
                    [
                        LLMMessage(role="system", content=TARGET_EXTRACTION_PROMPT),
                        LLMMessage(role="user", content=message),
                    ],
                    schema=TargetConcept,
                    max_tokens=100,
                    temperature=0.0,
                )
            except LLMError as error:
                tools.logger.log("extract_target_concept", f"llm failed: {error}")
                return None
            name = extracted.concept_name.strip()
            if name:
                concept, created = tools.resolver.resolve(name)
                tools.logger.log(
                    "extract_target_concept", f"message -> {concept.name!r} (created={created})"
                )
                return concept
        return None

    def _suggest_prerequisites(self, concept: Concept, tools: ToolSet) -> None:
        """Ask the LLM which prerequisites a fresh concept should have (spec §4)."""
        try:
            suggested = self.llm.structured_generate(
                [
                    LLMMessage(role="system", content=PREREQUISITE_SUGGESTION_PROMPT),
                    LLMMessage(role="user", content=f"Concept: {concept.name}"),
                ],
                schema=PrerequisiteSuggestions,
                max_tokens=300,
                temperature=0.0,
            )
        except LLMError as error:
            tools.logger.log("suggest_prerequisites", f"llm failed: {error}")
            return
        tools.logger.log(
            "suggest_prerequisites",
            f"concept={concept.name!r} -> {suggested.prerequisites[:5]}",
        )
        for name in suggested.prerequisites[:5]:
            if name.casefold() == concept.name.casefold():
                continue
            tools.create_relationship(name, concept.name, "PREREQUISITE_OF", 0.7)

    def _explain(self, concept: Concept, tools: ToolSet) -> str:
        excerpts = "\n\n".join(chunk.text[:1500] for chunk in concept.source_chunks[:3])
        if self.llm is not None:
            try:
                explanation = self.llm.generate(
                    [
                        LLMMessage(role="system", content=EXPLANATION_SYSTEM_PROMPT),
                        LLMMessage(
                            role="user",
                            content=(
                                f"Concept: {concept.name}\n"
                                f"Stored description: {concept.description or 'none'}\n\n"
                                f"Source excerpts:\n{excerpts or 'none provided'}"
                            ),
                        ),
                    ],
                    max_tokens=800,
                    temperature=0.4,
                )
                tools.logger.log("explain", f"concept={concept.name!r} (llm)")
                return explanation
            except LLMError as error:
                tools.logger.log("explain", f"llm failed, falling back: {error}")
        tools.logger.log("explain", f"concept={concept.name!r} (deterministic)")
        if concept.description:
            return f"{concept.name}: {concept.description}"
        return f"{concept.name}: " + (
            concept.source_chunks[0].text[:600]
            if concept.source_chunks
            else "(no material available yet)"
        )

    @staticmethod
    def _gap_reason(status: str) -> str:
        if status == UNKNOWN:
            return "no mastery evidence yet"
        return "estimated mastery is weak"

    @staticmethod
    def _format_mastery(mastery: float | None) -> str:
        return f"{mastery:.0%}" if mastery is not None else "no evidence"
