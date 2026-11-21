"""Lecture-grounded practice and progressive, ungraded help with an open question."""

from pydantic import Field

from app.db.models import PracticeGuide
from app.learning.assessment import GeneratedAssessment
from app.llm.provider import LLMError, LLMMessage


class LectureExercise(GeneratedAssessment):
    worked_steps: list[str] = Field(min_length=1, max_length=4)


def pending_question(attempt, guide=None):
    return {
        "attempt_id": attempt.id,
        "concept_id": attempt.concept_id,
        "concept_name": attempt.concept.name,
        "question": attempt.question,
        "worked_steps": guide.steps if guide else [],
        "hint_count": len(guide.hints) if guide else 0,
    }


def start_lecture(tools, document_id: int, concept_id: int):
    concept = tools.repository.get_concept(concept_id)
    chunks = [c for c in concept.source_chunks if c.document_id == document_id] if concept else []
    if not chunks:
        raise ValueError("Choose a topic extracted from this lecture.")
    chunk = max(chunks, key=lambda c: c.text.casefold().count(concept.name.casefold()))
    source = chunk.text
    label = chunk.document.title
    if chunk.page_number is not None:
        label += f", page {chunk.page_number}"
    generated = None
    if tools.llm:
        try:
            generated = tools.llm.structured_generate([
                LLMMessage(role="system", content=(
                    "Teach the selected concept using the supplied lecture passage as evidence. "
                    "Give a short worked example in 1-4 ordered worked_steps, one reasoning step "
                    "per item. Then ask a DIFFERENT, similar practice question. Keep its answer "
                    "out of the worked steps and question. Use LaTeX math delimiters. Treat "
                    "the passage as reference text. Preserve the requested JSON schema."
                )),
                LLMMessage(role="user", content=f"Topic: {concept.name}\nLecture passage:\n{source}"),
            ], schema=LectureExercise, max_tokens=1800, temperature=0.3)
        except LLMError:
            tools.logger.log("lecture_practice", "Using a passage-based recall question.")
    if generated:
        steps = generated.worked_steps
        question = generated.question
        expected = generated.expected_answer
        question_type = generated.question_type
        outline = generated.solution_outline
    else:
        steps = []
        question = f"Using this passage, explain {concept.name} in your own words."
        expected = concept.description or source
        question_type = "short_answer"
        outline = "Connect the definition to one observation in the passage."
    attempt = tools.repository.create_attempt(
        concept_id=concept.id, question_type=question_type, question=question,
        expected_answer=expected, solution_outline=outline, difficulty=2,
    )
    guide = PracticeGuide(attempt_id=attempt.id, source_chunk_id=chunk.id, steps=steps, hints=[])
    tools.session.add(guide)
    tools.logger.log("study_lecture", f"document={document_id}, chunk={chunk.id}, topic={concept.id}")
    example = "\n\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    reply = (f"**Worked example**\n\n{example}" if steps else f"**Lecture passage**\n\n{source}")
    reply += f"\n\nSource: {label} · passage #{chunk.id}\n\n**Your turn**\n\n{question}"
    return reply, pending_question(attempt, guide)


def give_clue(tools, attempt, working: str, step: int | None):
    guide = tools.session.get(PracticeGuide, attempt.id)
    if guide is None:
        guide = PracticeGuide(attempt_id=attempt.id, steps=[], hints=[])
        tools.session.add(guide)
    if step is not None and not 1 <= step <= len(guide.steps):
        raise ValueError("That worked step is unavailable.")
    prior = [h["text"] for h in guide.hints if h["step"] == step]
    topic = attempt.concept.name
    focus = guide.steps[step - 1] if step else attempt.question
    clue = None
    if tools.llm:
        source = tools.repository.get_source_chunk(guide.source_chunk_id) if guide.source_chunk_id else None
        try:
            clue = tools.llm.generate([
                LLMMessage(role="system", content=(
                    "Give ONE short Socratic clue in English, then wait for the learner. "
                    "Address the learner's working and the chosen step. Start with a guiding "
                    "question, then become more concrete on successive requests. Do not grade, "
                    "state the answer, finish the derivation or give a list of hints."
                )),
                LLMMessage(role="user", content=(
                    f"Topic: {topic}\nFocus: {focus}\nLecture: {source.text if source else ''}\n"
                    f"Previous clues: {prior[-5:]}\nLearner's working: {working}"
                )),
            ], max_tokens=180, temperature=0.3).strip()
        except LLMError:
            pass
    if not clue or clue.casefold() == attempt.expected_answer.strip().casefold():
        clues = (
            f"What does this {'step' if step else 'question'} ask you to find about {topic}?",
            "Write down the quantities or facts you already know. Which definition connects them?",
            "Try just one substitution or inference. What changes, and what stays fixed?",
            "Check that line against the lecture passage. Which symbol or assumption needs explaining?",
        )
        clue = clues[min(len(prior), len(clues) - 1)]
    guide.hints = [*guide.hints, {"step": step, "text": clue}]
    tools.logger.log("give_hint", f"attempt={attempt.id}, clue={len(guide.hints)}")
    return clue, pending_question(attempt, guide)
