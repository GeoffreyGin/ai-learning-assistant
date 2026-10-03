# AI Personal Knowledge Engineer
## Software Specification — MVP

## 1. Product Definition

Build an AI agent that maintains a **long-term model of a user's knowledge**.

The system ingests the user's learning materials, extracts concepts and relationships, builds a knowledge graph, estimates mastery from actual interactions, identifies prerequisite gaps, and generates targeted learning activities.

### Core product principle

The product is **not**:

> "ChatGPT that can read my PDFs."

The product is:

> **"An AI agent that maintains a model of what I know, identifies what I am missing, and helps me close those gaps."**

The system should become more useful as the user accumulates more documents and completes more exercises.

---

# 2. Core User Flow

The main loop is:

```text
User adds material
        ↓
Extract concepts
        ↓
Connect concepts to existing knowledge
        ↓
Update knowledge graph
        ↓
User chooses learning goal
        ↓
Find prerequisite gaps
        ↓
Generate targeted learning task
        ↓
User answers / solves
        ↓
Evaluate performance
        ↓
Update mastery
        ↓
Recommend next action
```

---

# 3. MVP Goals

The MVP must support these five capabilities:

### A. Knowledge ingestion

Import local:

- PDF
- Markdown
- TXT

The system extracts useful concepts and stores their source locations.

### B. Knowledge graph

Represent:

- concepts
- relationships
- prerequisites
- sources

Example:

```text
Brownian Motion
      ↓ prerequisite
Stochastic Processes
      ↓ prerequisite
Ito's Lemma
      ↓ prerequisite
Black-Scholes
```

### C. Mastery tracking

Maintain a mastery estimate for each concept based on:

- quiz answers
- problem-solving performance
- repeated mistakes
- recency
- confidence

Do NOT let the LLM arbitrarily assign mastery percentages without evidence.

### D. Gap detection

Given a target concept, determine:

1. which prerequisites exist
2. which prerequisites appear mastered
3. which prerequisites are weak
4. which prerequisites are missing

### E. Targeted learning

Generate:

- explanations
- questions
- exercises
- review recommendations

The content must target the user's actual weak points.

---

# 4. Example

The user uploads material about:

```text
Calculus
Brownian Motion
Geometric Brownian Motion
Black-Scholes
```

The graph becomes:

```text
Calculus
   ↓
Brownian Motion
   ↓
Geometric Brownian Motion
   ↓
Black-Scholes
```

The system also determines that Black-Scholes normally depends on Ito's Lemma.

If Ito's Lemma is missing, the user asks:

> "Help me learn Black-Scholes."

The system should respond with something conceptually like:

```text
Target:
Black-Scholes

Prerequisites:
Calculus             MASTERED
Brownian Motion      MASTERED
Geometric BM         MASTERED
Ito's Lemma          MISSING

Recommendation:
Learn Ito's Lemma before continuing.
```

It should then generate a short learning sequence for Ito's Lemma.

---

# 5. Product Differentiation

Do not optimize the project around document Q&A.

The system must emphasize:

### Long-term memory
Knowledge persists across sessions.

### Knowledge graph
Concepts and relationships are stored explicitly.

### User model
The system tracks evidence about what the user understands.

### Gap detection
The agent identifies missing prerequisites instead of merely answering questions.

### Proactive learning
The system can recommend what to study next.

### Evidence-based mastery
Mastery comes from interactions and results, not from arbitrary LLM guesses.

---

# 6. Non-Goals for MVP

Do NOT build these initially:

- full-featured web search engine
- multi-user SaaS
- mobile app
- complex multi-agent architecture
- autonomous internet browsing
- voice interface
- automatic email/calendar integration
- advanced graph database
- sophisticated recommendation model
- fully autonomous learning without user interaction
- generic "ask anything" chatbot as the primary feature

The MVP should be a focused personal knowledge system.

---

# 7. Recommended Tech Stack

Use Python.

### Backend

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy or SQLModel
- SQLite

### Knowledge graph

Start with:

- NetworkX for graph operations

Do NOT introduce Neo4j unless the data model becomes too large for the MVP.

### LLM

Use an LLM provider through an abstraction layer.

Prefer an OpenAI-compatible implementation, but do not hard-code the entire application around one provider.

Create:

```python
LLMProvider
```

with methods such as:

```python
generate()
structured_generate()
```

### Embeddings

For MVP:

- use embeddings only where they provide clear value
- store vectors locally or through a simple vector store

Do not make vector search the foundation of the product.

The knowledge graph and relational database are the primary source of truth.

### Frontend

For MVP, use a lightweight frontend.

Preferred:

- React + TypeScript

However, functionality is more important than visual polish.

---

# 8. High-Level Architecture

```text
                    ┌───────────────┐
                    │     User      │
                    └───────┬───────┘
                            │
                            ↓
                    ┌───────────────┐
                    │  API / UI     │
                    └───────┬───────┘
                            │
                            ↓
                    ┌───────────────┐
                    │ Agent Layer   │
                    └───────┬───────┘
                            │
          ┌─────────────────┼──────────────────┐
          ↓                 ↓                  ↓
   Document Engine    Knowledge Engine   Learning Engine
          │                 │                  │
          ↓                 ↓                  ↓
      Documents       Knowledge Graph      Assessments
      Extraction      Concepts            Mastery
      Chunking        Relations            Exercises
          │                 │                  │
          └─────────────────┼──────────────────┘
                            ↓
                     ┌─────────────┐
                     │   SQLite    │
                     └─────────────┘
```

---

# 9. Repository Structure

Use a clean modular structure:

```text
ai-knowledge-engineer/
│
├── app/
│   ├── api/
│   │   ├── routes_documents.py
│   │   ├── routes_knowledge.py
│   │   ├── routes_learning.py
│   │   └── routes_chat.py
│   │
│   ├── agent/
│   │   ├── controller.py
│   │   ├── prompts.py
│   │   └── tools.py
│   │
│   ├── knowledge/
│   │   ├── extractor.py
│   │   ├── graph.py
│   │   ├── resolver.py
│   │   └── gap_detector.py
│   │
│   ├── learning/
│   │   ├── mastery.py
│   │   ├── assessment.py
│   │   ├── exercise_generator.py
│   │   └── recommender.py
│   │
│   ├── ingestion/
│   │   ├── pdf.py
│   │   ├── markdown.py
│   │   ├── text.py
│   │   └── pipeline.py
│   │
│   ├── db/
│   │   ├── models.py
│   │   ├── database.py
│   │   └── repositories.py
│   │
│   ├── llm/
│   │   ├── provider.py
│   │   └── openai_provider.py
│   │
│   └── main.py
│
├── frontend/
│
├── tests/
│
├── data/
│
├── scripts/
│
├── README.md
├── pyproject.toml
└── .env.example
```

---

# 10. Data Model

Implement the following core entities.

## Document

```python
Document:
    id
    title
    file_path
    file_type
    created_at
```

## SourceChunk

A document should be split into source chunks.

```python
SourceChunk:
    id
    document_id
    text
    page_number
    chunk_index
```

Every extracted concept must be traceable to one or more source chunks.

---

## Concept

```python
Concept:
    id
    name
    description
    created_at
    updated_at
```

Concept names should be normalized to avoid duplicates such as:

```text
"Ito Lemma"
"Ito's Lemma"
"Itô's lemma"
```

These should resolve to the same concept where appropriate.

---

## Relationship

```python
Relationship:
    id
    source_concept_id
    target_concept_id
    relation_type
    confidence
    evidence_source_id
```

Supported MVP relationship types:

```text
PREREQUISITE_OF
RELATED_TO
PART_OF
EXAMPLE_OF
DERIVED_FROM
CONTRADICTS
```

---

## MasteryRecord

Do not store only one opaque number.

Track evidence.

```python
MasteryRecord:
    id
    concept_id
    estimated_mastery
    evidence_count
    correct_count
    incorrect_count
    last_tested_at
    updated_at
```

---

## AssessmentAttempt

```python
AssessmentAttempt:
    id
    concept_id
    question
    user_answer
    expected_answer
    result
    difficulty
    created_at
```

---

# 11. Ingestion Pipeline

When a user uploads a document:

```text
Upload
 ↓
Parse
 ↓
Chunk
 ↓
Extract concepts
 ↓
Extract relationships
 ↓
Resolve duplicate concepts
 ↓
Store concepts
 ↓
Store relationships
 ↓
Attach source evidence
```

The extraction output must use structured JSON.

Example:

```json
{
  "concepts": [
    {
      "name": "Brownian Motion",
      "description": "..."
    },
    {
      "name": "Ito's Lemma",
      "description": "..."
    }
  ],
  "relationships": [
    {
      "source": "Brownian Motion",
      "target": "Ito's Lemma",
      "type": "PREREQUISITE_OF",
      "confidence": 0.86
    }
  ]
}
```

The application must validate this JSON before storing it.

---

# 12. Concept Resolution

This is an important part of the system.

When extracting a new concept:

```text
New concept
    ↓
Search existing concepts
    ↓
Find likely matches
    ↓
LLM / similarity check
    ↓
Merge or create
```

Do not allow large numbers of duplicate concepts.

Example:

```text
Existing:
Black-Scholes Model

New:
Black Scholes model

→ merge
```

But:

```text
Black-Scholes Model
Black-Scholes PDE

→ keep separate
```

---

# 13. Agent Tools

The agent should have explicit tools.

Minimum tool set:

```python
search_concepts(query)
get_concept(concept_id)
get_prerequisites(concept_id)
get_related_concepts(concept_id)

search_documents(query)
get_source_chunk(chunk_id)

get_user_mastery(concept_id)
record_assessment(...)
generate_assessment(...)
recommend_next_topic(...)

create_concept(...)
create_relationship(...)
update_concept(...)
```

Tool calls should be explicit and logged.

---

# 14. Agent Behavior

The agent should not immediately answer everything with an LLM-generated explanation.

For a learning request:

```text
User:
"I want to learn X."
```

The agent should:

```text
1. Find X
2. Retrieve prerequisite graph
3. Retrieve mastery evidence
4. Identify gaps
5. Rank the gaps
6. Decide what to teach first
7. Generate learning content
8. Test the user
9. Update mastery
10. Recommend next step
```

This decision process is the core agent behavior.

---

# 15. Gap Detection

Implement a deterministic first version.

For a target concept:

```text
target
 ↓
traverse prerequisite relationships
 ↓
collect prerequisite concepts
 ↓
retrieve mastery
 ↓
classify:
    MASTERED
    WEAK
    UNKNOWN
```

Initial thresholds:

```text
MASTERED >= 0.80
WEAK      0.40–0.79
UNKNOWN   < 0.40 or insufficient evidence
```

These thresholds should be configurable.

Do not claim the system knows the user's true ability.

Instead, call it:

> estimated mastery based on observed evidence.

---

# 16. Mastery Updating

Start with a simple evidence-based update.

Example:

```text
previous mastery = 0.60

correct answer:
mastery increases

incorrect answer:
mastery decreases

repeated correct answers:
mastery increases more slowly

long time without practice:
mastery decays slightly
```

Do not allow large jumps from one question.

The algorithm should be deterministic and unit-tested.

---

# 17. Assessment Generation

The LLM should generate structured questions.

Example schema:

```json
{
  "concept": "Ito's Lemma",
  "difficulty": 2,
  "question_type": "calculation",
  "question": "...",
  "expected_answer": "...",
  "solution_outline": "..."
}
```

Supported MVP question types:

```text
conceptual
calculation
application
true_false
short_answer
```

The system should avoid generating questions outside the selected concept.

---

# 18. Answer Evaluation

For objective questions:

Use deterministic checking where possible.

Examples:

- numeric answers
- multiple choice
- algebraic equivalence

For open-ended answers:

Use the LLM, but require structured output:

```json
{
  "correct": true,
  "score": 0.8,
  "reasoning": "...",
  "identified_mistakes": [
    "..."
  ]
}
```

The system should store the evaluation.

---

# 19. Source Grounding

Every factual explanation derived from a user's material should be traceable to source chunks.

The UI should allow the user to see:

```text
Claim
 ↓
Source
 ↓
Document
 ↓
Page
```

Avoid presenting unsupported extracted facts as authoritative.

When the agent is uncertain, it should explicitly mark the uncertainty.

---

# 20. Chat Interface

The system may include a conversational interface, but chat is NOT the main product.

Good:

> "What do I need to know before learning Fourier transforms?"

> "Why am I struggling with this topic?"

> "Test me on the concepts I got wrong yesterday."

Bad:

> "Tell me a joke."

> "Write an essay about the French Revolution."

The application is a knowledge-management and learning agent, not a general-purpose chatbot.

---

# 21. Main UI Screens

MVP should contain four main screens.

## Dashboard

Show:

```text
Recently added knowledge
Weak concepts
Current learning goal
Recommended next topic
Recent assessments
```

## Knowledge Graph

Show:

```text
Concept nodes
Prerequisite edges
Related concepts
Mastery state
```

Allow clicking a concept to inspect it.

## Learning

Show:

```text
Current target
Prerequisite gaps
Exercises
Results
Recommendations
```

## Documents

Show:

```text
Uploaded files
Extracted concepts
Source references
Processing status
```

---

# 22. Example Dashboard

```text
========================================
       AI PERSONAL KNOWLEDGE ENGINEER
========================================

Current Goal
> Learn Black-Scholes

Prerequisite Status

✓ Calculus
✓ Brownian Motion
✓ Geometric Brownian Motion
△ Multivariable Chain Rule
✗ Ito's Lemma

Recommended Next Step
> Review Ito's Lemma

Weak Concepts

Ito's Lemma          42%
PDEs                 57%
Risk-Neutral Pricing 61%

Recent Activity

✓ 4/5 Brownian Motion questions
✗ 2/5 Ito's Lemma questions
✓ 5/5 Geometric BM questions
```

---

# 23. API Endpoints

Implement basic endpoints.

```text
POST   /documents/upload
GET    /documents
GET    /documents/{id}

GET    /concepts
GET    /concepts/{id}

GET    /concepts/{id}/prerequisites
GET    /concepts/{id}/related

GET    /learning/gaps/{concept_id}
GET    /learning/recommendation

POST   /assessment/generate
POST   /assessment/submit

POST   /agent/chat
```

---

# 24. Logging

Every important agent action should be logged.

Example:

```text
2026-09-21
Agent action:
searched concept "Ito's Lemma"

Agent action:
found 3 prerequisites

Agent action:
identified "multivariable chain rule" as weak

Agent action:
generated 5 exercises

Agent action:
updated mastery from 0.41 → 0.48
```

This is important for debugging the agent.

---

# 25. Error Handling

The system must handle:

- malformed PDFs
- unsupported file types
- LLM API failures
- invalid structured output
- duplicate concepts
- contradictory relationships
- missing source references
- database failures

LLM output must never be trusted blindly.

Validate all structured output before database writes.

---

# 26. Testing Requirements

Write automated tests for:

### Knowledge graph

```text
create concept
merge concept
create relationship
find prerequisites
traverse graph
```

### Mastery

```text
correct answer increases mastery
incorrect answer decreases mastery
mastery stays within [0,1]
```

### Gap detection

```text
missing prerequisite detected
weak prerequisite detected
mastered prerequisite ignored
```

### Ingestion

```text
document parsed
concepts extracted
sources preserved
```

### API

Test all major endpoints.

---

# 27. MVP Acceptance Criteria

The MVP is complete when this workflow works end-to-end:

```text
1. Upload PDF
        ↓
2. Extract concepts
        ↓
3. Build graph
        ↓
4. User chooses target concept
        ↓
5. System identifies prerequisites
        ↓
6. System checks estimated mastery
        ↓
7. System identifies knowledge gaps
        ↓
8. System generates targeted exercise
        ↓
9. User submits answer
        ↓
10. System evaluates answer
        ↓
11. Mastery updates
        ↓
12. System recommends next action
```

A user should be able to complete this entire loop without manually editing the database.

---

# 28. Example End-to-End Scenario

Input:

```text
PDF:
"Introduction to Quantitative Finance"
```

The system extracts:

```text
Probability
Calculus
Brownian Motion
Stochastic Processes
Ito's Lemma
Geometric Brownian Motion
Black-Scholes
```

User selects:

> Learn Black-Scholes.

The system finds:

```text
Calculus            MASTERED
Probability         MASTERED
Brownian Motion     MASTERED
Stochastic Process  WEAK
Ito's Lemma         UNKNOWN
Geometric BM        WEAK
```

The agent recommends:

```text
1. Review stochastic processes
2. Learn Ito's Lemma
3. Review geometric Brownian motion
4. Attempt Black-Scholes assessment
```

The user completes the exercises.

The system updates:

```text
Ito's Lemma:
0.20 → 0.46

Geometric BM:
0.52 → 0.71
```

The next recommendation is recalculated automatically.

---

# 29. Agent Design Principles

Follow these rules throughout implementation.

### Rule 1
The database/knowledge graph is the source of truth for persistent knowledge.

### Rule 2
The LLM handles language understanding and reasoning, not basic deterministic logic.

### Rule 3
Use deterministic code whenever a task can be done deterministically.

### Rule 4
All extracted knowledge should retain source evidence.

### Rule 5
Do not invent mastery without evidence.

### Rule 6
Prefer small, observable agent steps over one giant autonomous prompt.

### Rule 7
Every tool call should be inspectable and logged.

### Rule 8
Do not overbuild the UI before the knowledge loop works.

---

# 30. Development Plan

## Phase 1 — Foundation

Build:

- database
- document upload
- PDF/Markdown/TXT parser
- concept model
- source chunks
- basic API

Goal:

```text
document → stored concepts
```

## Phase 2 — Knowledge Graph

Build:

- relationships
- concept resolution
- prerequisite traversal
- graph visualization

Goal:

```text
documents → knowledge graph
```

## Phase 3 — Learning Model

Build:

- mastery records
- assessments
- answer evaluation
- gap detection

Goal:

```text
knowledge graph + user performance
```

## Phase 4 — Agent

Build:

- agent controller
- tool system
- planning loop
- learning recommendations

Goal:

```text
user goal → agent investigates → targeted learning
```

## Phase 5 — Polish

Add:

- dashboard
- logging UI
- improved graph visualization
- better prompts
- better error handling
- evaluation metrics

---

# 31. Future Features

Do not implement these in MVP, but design the architecture so they are possible later.

### Proactive agent

The system notices:

```text
"You repeatedly make mistakes with eigenvectors."
```

and proactively schedules review.

### Spaced repetition

Automatically schedule review based on previous performance.

### Web research

Allow the agent to discover external material to fill missing gaps.

### Contradiction detection

Detect conflicting claims between sources.

### Multi-agent architecture

Possible agents:

```text
Research Agent
Knowledge Agent
Teacher Agent
Evaluator Agent
Planner Agent
```

Only add this after the single-agent system works.

### Long-term learning analytics

Show:

```text
concept growth
weakness trends
retention
learning efficiency
```

---

# 32. Evaluation Metrics

Do not judge the system only by how good its generated text sounds.

Track:

### Knowledge extraction

- concept precision
- duplicate rate
- relationship accuracy

### Gap detection

- percentage of identified gaps confirmed by user performance
- false positive gap rate

### Learning

- pre-test score
- post-test score
- retention after repeated testing

### Agent quality

- successful tool-call rate
- task completion rate
- invalid LLM output rate
- average number of steps per task

The most important metric is:

> **Does targeted intervention improve the user's performance on the weak concept?**

---

# 33. Coding Instructions for Codex

Implement the project incrementally.

Do not attempt to build the entire system in one step.

Start with:

```text
Phase 1
Database + ingestion + concepts
```

Then verify tests pass.

Then implement:

```text
Phase 2
Knowledge graph
```

Then:

```text
Phase 3
Mastery + gap detection
```

Then:

```text
Phase 4
Agent
```

At every phase:

1. write tests
2. implement functionality
3. run tests
4. fix failures
5. update README
6. keep the code modular

Do not introduce unnecessary dependencies.

Prefer simple implementations first.

Every major feature should have a clear interface so that later components can replace the initial implementation without rewriting the entire application.

---

# 34. Definition of Success

The finished project should make this statement true:

> **A user can upload their learning materials, choose something they want to understand, and the system can determine what they already know, identify the prerequisite gaps preventing them from understanding it, teach those gaps, test the user, and update its understanding of the user's knowledge over time.**

That is the core product.

Everything else is secondary.
