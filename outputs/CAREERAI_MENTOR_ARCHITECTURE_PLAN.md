# CareerAI Mentor — Architecture & Development Plan

## 1. Architecture

CareerAI Mentor is a modular monolith for the first production release: a React single-page application communicates with a FastAPI API, which owns transactional data, orchestration, document ingestion, and retrieval. This keeps deployment and local development simple while maintaining clear boundaries that can later be extracted into workers or services.

```text
React + Vite (TypeScript)
  ├─ public routes: landing, login, register
  └─ protected routes: onboarding, dashboard, roadmap, practice, interview
          │ HTTPS / JWT
FastAPI API
  ├─ routers → service layer → SQLAlchemy repositories → SQLite/PostgreSQL
  ├─ auth, validation, error handling, file validation
  ├─ resume ingestion (PDF/DOCX/TXT)
  ├─ LangGraph coordinator and specialist agents
  └─ RAG service → embeddings → FAISS indices
          │
Groq LLM (primary) / Hugging Face (configured fallback)
```

### Core design decisions

- **Modular monolith:** API domains remain independently testable and are grouped by feature; no network hop is introduced until scale demands it.
- **Async work boundary:** parsing, embedding/index updates, and longer AI evaluations run through a job abstraction. Development may execute jobs in-process; production can plug in a worker/queue without changing API contracts.
- **Provider abstraction:** `LLMProvider` and `EmbeddingProvider` interfaces isolate Groq, Hugging Face, and local/model changes.
- **Source-aware AI:** every generated recommendation stores the model/provider, prompt-template version, retrieval source identifiers, and a user-visible rationale. AI outputs are schema-validated before persistence.
- **Authoritative scoring:** readiness, skill, quiz, and interview scores are calculated by backend services from real attempts and evaluations—not seeded frontend values.
- **Storage abstraction:** SQLite is used locally through SQLAlchemy; migrations and configuration must also support PostgreSQL. Uploaded original files use a configurable storage adapter, never the database blob layer by default.

### Security baseline

- Passwords use Argon2 or bcrypt through a dedicated password service; only password hashes are stored.
- Short-lived signed JWT access tokens protect all student resources. Refresh-token/session support is planned before public production launch.
- APIs authorize by authenticated user ownership on every resource query, not just route protection.
- CORS uses explicit environment-configured origins; no wildcard in production.
- Resume uploads allow only PDF, DOCX, and TXT, enforce size and MIME/content checks, generate server-side names, and never execute uploaded content.
- Secrets (`GROQ_API_KEY`, `HF_API_KEY`, JWT secret, database URL) live only in server-side environment variables and are excluded from version control.
- Pydantic request models, centralized exception handlers, structured audit logs, rate limits on authentication/AI endpoints, and dependency scanning are required before release.

## 2. Proposed Folder Structure

```text
careerai-mentor/
├─ frontend/
│  ├─ src/
│  │  ├─ api/                 # Axios client and typed endpoint modules
│  │  ├─ components/          # Reusable presentational components
│  │  ├─ features/            # dashboard, onboarding, roadmap, practice, interview
│  │  ├─ hooks/
│  │  ├─ layouts/
│  │  ├─ pages/
│  │  ├─ routes/              # router and protected-route guard
│  │  ├─ types/
│  │  ├─ utils/
│  │  └─ main.tsx
│  ├─ tests/
│  ├─ .env.example
│  └─ vite.config.ts
├─ backend/
│  ├─ app/
│  │  ├─ api/routers/         # thin HTTP controllers by domain
│  │  ├─ core/                # config, security, logging, exceptions
│  │  ├─ db/                  # engine, base, migrations integration
│  │  ├─ models/              # SQLAlchemy models
│  │  ├─ schemas/             # Pydantic input/output models
│  │  ├─ repositories/        # persistence queries
│  │  ├─ services/            # business logic and score calculation
│  │  ├─ agents/              # LangGraph state, nodes, prompts, tools
│  │  ├─ rag/                 # loaders, chunking, embeddings, FAISS, retrieval
│  │  ├─ integrations/        # Groq/Hugging Face/storage adapters
│  │  ├─ jobs/                # async-work interface and handlers
│  │  └─ main.py
│  ├─ alembic/
│  ├─ tests/
│  ├─ data/                   # local, gitignored FAISS/runtime data
│  └─ .env.example
├─ docs/
├─ docker/
├─ docker-compose.yml
├─ Dockerfile.backend
├─ Dockerfile.frontend
└─ README.md
```

## 3. Database Design

All tables have `id`, `created_at`, and `updated_at` unless noted. UUID primary keys are recommended. Foreign keys, ownership indexes, and migration-managed constraints are mandatory.

| Model | Purpose and key fields | Relationships |
|---|---|---|
| User | `email` (unique), `password_hash`, `role`, `is_active`, `last_login_at` | one student profile; owns student data |
| StudentProfile | `user_id` (unique), name, college, graduation_year, branch, bio, preferred_learning_style, target_role_id | belongs to User; target JobRole |
| Resume | `user_id`, `storage_key`, `original_filename`, `mime_type`, `size_bytes`, `status`, `parsed_text`, `parsed_at` | belongs to User; source for extracted skills |
| Skill | canonical `name` (unique), `category`, description | referenced by gaps, questions, resources |
| SkillGap | `user_id`, `skill_id`, `target_role_id`, `current_score`, `target_score`, `gap_score`, `evidence_json`, `status` | unique per user/skill/role context |
| JobRole | title, `slug` (unique), description, `required_skills_json`, experience_level | has descriptions and roadmaps |
| JobDescription | `job_role_id`, company, title, source URL, content, `is_active` | retrieval source and analysis input |
| Roadmap | `user_id`, `job_role_id`, title, status, generated_by, version, starts/target dates | has ordered RoadmapTasks |
| RoadmapTask | `roadmap_id`, `skill_id` nullable, title, description, sequence, difficulty, estimated_minutes, status, due_date | belongs to Roadmap; progress input |
| Question | `skill_id`, type, difficulty, prompt, options JSON nullable, expected_answer, explanation, provenance | has attempts; RAG/AI generated or curated |
| QuestionAttempt | `user_id`, `question_id`, answer, is_correct, score, duration_seconds, evaluated_at | performance event |
| MockInterview | `user_id`, `job_role_id`, status, difficulty, started/ended timestamps, overall_score, transcript_version | has InterviewAnswers and Feedback |
| InterviewAnswer | `mock_interview_id`, sequence, question, answer_text, rubric_json, score, evaluation_json | belongs to MockInterview |
| Feedback | `user_id`, `mock_interview_id` nullable, `question_attempt_id` nullable, type, summary, strengths JSON, improvements JSON, score | structured guidance; source-linked |
| ProjectRecommendation | `user_id`, `job_role_id`, title, description, difficulty, skills_json, rationale, status | personalized recommendation |
| LearningResource | title, URL, provider, format, skill metadata JSON, level, quality/status | reusable catalog, retrievable |
| Progress | `user_id`, date, readiness_score, roadmap_completion, quiz_accuracy, interview_score, skill_snapshot_json | one daily aggregate per user |
| UserActivity | `user_id`, event_type, entity_type, entity_id, metadata_json, occurred_at | chronological dashboard feed/audit trail |

Important constraints: `User.email`, `Skill.name`, and `JobRole.slug` are unique; roadmap task sequence is unique within each roadmap; `Progress(user_id, date)` is unique. Index `user_id` on every user-owned table, plus `SkillGap(user_id, target_role_id)` and `QuestionAttempt(user_id, evaluated_at)`.

## 4. API Design

Base path: `/api/v1`. JSON is the default; resume upload is `multipart/form-data`. All protected endpoints use `Authorization: Bearer <access_token>` and return a consistent error body: `{ "error": { "code", "message", "details", "request_id" } }`.

| Domain | Endpoint | Intent |
|---|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` | identity and session lifecycle |
| Profile | `GET/PATCH /profile`, `POST /profile/onboarding` | read/update career preferences and target role |
| Resume | `POST /resumes`, `GET /resumes`, `GET /resumes/{id}`, `DELETE /resumes/{id}`, `POST /resumes/{id}/analyze` | validated upload and analysis job |
| Roles | `GET /job-roles`, `GET /job-roles/{id}`, `POST /job-descriptions/analyze` | role catalog and supplied-JD analysis |
| Analysis | `POST /skill-gaps/analyze`, `GET /skill-gaps` | initiate and view role-specific skill gaps |
| Roadmaps | `POST /roadmaps/generate`, `GET /roadmaps`, `GET/PATCH /roadmaps/{id}`, `PATCH /roadmap-tasks/{id}` | roadmap generation and task completion |
| Practice | `POST /practice/sessions`, `GET /practice/questions`, `POST /questions/{id}/attempts`, `GET /practice/analytics` | adaptive practice and real performance |
| Interviews | `POST /mock-interviews`, `POST /mock-interviews/{id}/answers`, `POST /mock-interviews/{id}/complete`, `GET /mock-interviews/{id}` | interview lifecycle and evaluation |
| Recommendations | `GET /recommendations/today`, `GET /project-recommendations`, `POST /project-recommendations/generate`, `GET /learning-resources` | personalized next actions/resources |
| Dashboard | `GET /dashboard/summary`, `GET /progress`, `GET /activities` | charts, aggregates, and activity feed |
| System | `GET /health`, `GET /ready` | deployment health checks |

Mutating endpoints validate ownership and inputs, return typed Pydantic response schemas, and use `202 Accepted` plus a job/status resource for long-running analysis. Pagination (`limit`, `cursor`) applies to collections; user-facing generated results include `status` and `generated_at`.

## 5. LangGraph Workflow

The graph is invoked by explicitly requested actions or job handlers, not on every dashboard view. `MentorState` contains: authenticated `user_id`, action, profile/resume facts, target role, job-description facts, retrieved context, performance summary, specialist outputs, validation errors, and trace metadata. Raw resumes and secrets are excluded from graph state and prompts unless necessary, and only retrieved excerpts are included.

```text
START → load_student_context → Coordinator
  ├─ profile_update/resume_analysis → Profile Agent → persist facts → Coordinator
  ├─ gap_analysis → Skill Gap Agent → persist SkillGaps → Coordinator
  ├─ roadmap_generation → Roadmap Agent → validate/persist Roadmap → END
  ├─ practice_generation → Question Agent → validate/persist Questions → END
  ├─ interview_turn → Mock Interview Agent → Feedback Agent → persist → END
  ├─ project_recommendation → Project Recommendation Agent → persist → END
  └─ daily_adaptation → Feedback Agent → persist recommendation/progress → END
```

Each specialist uses a shared retrieval tool scoped to its approved collections. A validator node checks JSON schema, grounding/provenance, required fields, and safe fallback behavior. If a provider fails or the answer cannot be validated, the graph records a recoverable failure and returns a transparent retry state; it never invents completed student results.

### RAG pipeline

1. Ingest curated job roles, job descriptions, interview questions, resources, project ideas, and technical concepts; sanitize and record source metadata.
2. Chunk by semantic headings with document, source, role, skill, and version metadata.
3. Create embeddings through `EmbeddingProvider`; store FAISS vector index plus a durable metadata mapping.
4. Retrieve by task, role, skills, difficulty, and metadata filters; apply relevance threshold and diversity selection.
5. Pass compact cited context to the agent. Persist retrieved source IDs with generated content for traceability.

FAISS is appropriate for local/development retrieval. Its index and metadata must be versioned together, rebuilt through an ingestion command, and treated as an environment-specific runtime artifact—not an authoritative relational database.

## 6. Agent Responsibilities

| Agent | Responsibility | Inputs | Outputs / guardrails |
|---|---|---|---|
| Coordinator | Route approved action to a specialist, manage shared state and validation/retry branches | action, state, job status | no career claims of its own; invokes only allowed tools |
| Profile Agent | Extract structured facts from onboarding/resume and resolve conflicts | profile, parsed resume, role | normalized profile facts, extracted skills, confidence/evidence; asks for review when uncertain |
| Skill Gap Agent | Compare observed skills against target role/JD expectations | profile facts, role, attempts, retrieved requirements | ranked gaps, target/current scores, evidence; never treats an inference as verified skill mastery |
| Roadmap Agent | Build sequenced, achievable learning plan | gaps, availability, resources, role | tasks, dependencies, estimates, milestones; uses available resources and dates realistically |
| Question Agent | Produce adaptive practice questions | target skills, weakness trend, difficulty, retrieved concepts | schema-valid questions/rubrics with provenance; excludes answers from prompts shown to students |
| Mock Interview Agent | Run role-appropriate, turn-aware interview session | role, level, prior answers, retrieved context | next question or rubric-ready interview state; avoids unsupported employment guarantees |
| Project Recommendation Agent | Recommend portfolio projects aligned to gaps/role | gaps, interests, resources | scoped project, milestones, skills, rationale; indicates effort assumptions |
| Feedback Agent | Evaluate performance and generate next best actions | attempts, answer rubrics, interview evaluations, progress | strengths, actionable improvements, score updates, daily recommendations; recalculates from evidence |

## 7. Development Phases

### Phase 0 — Foundation and decisions

- Initialize repository, environment examples, lint/format tooling, Docker setup, CI skeleton, and architecture decision records.
- Define API error envelope, config model, observability policy, migrations, and seed strategy for *catalog* data only.
- Exit criteria: frontend/backend run locally, health endpoints work, and no keys are committed.

### Phase 1 — Identity and onboarding

- Implement database base models, migrations, registration/login, password hashing, JWT, protected React routes, and typed Axios client.
- Build onboarding/profile and job-role selection backed by persisted data.
- Exit criteria: a user can register, authenticate, update only their profile, and access is covered by API tests.

### Phase 2 — Resume ingestion and profile analysis

- Add secure PDF/DOCX/TXT upload, parse pipeline, storage adapter, extraction schema, and human-reviewable profile facts.
- Exit criteria: valid files parse asynchronously; invalid/oversized uploads fail safely; raw files and extracted metadata are tested.

### Phase 3 — Knowledge base and RAG

- Implement ingestion, chunking, embedding provider, FAISS/metadata lifecycle, retrieval filters, and evaluation fixtures.
- Exit criteria: repeatable index build, source-aware retrieval, and retrieval quality tests for representative role/skill queries.

### Phase 4 — Skill gaps and roadmap

- Implement LangGraph coordinator, Profile/Skill Gap/Roadmap agents, score service, role/JD comparison, and roadmap UI.
- Exit criteria: a profile + target role yields stored, explainable gaps and a editable roadmap with no fabricated performance data.

### Phase 5 — Adaptive practice

- Implement Question and Feedback agents, question session/attempt APIs, difficulty adjustment, resource suggestions, and quiz analytics.
- Exit criteria: attempted questions update measured accuracy/skill evidence and influence subsequent question selection.

### Phase 6 — Mock interviews and projects

- Implement interview state machine, answer evaluation, feedback, project recommendations, and related views.
- Exit criteria: an interview persists its turns/evaluation and produces actionable, source-aware feedback.

### Phase 7 — Dashboard, quality, and release readiness

- Build dashboard charts from persisted aggregates, daily recommendation job, activity feed, accessibility, test coverage, performance/security testing, production PostgreSQL configuration, and deployment documentation.
- Exit criteria: Docker Compose deployment succeeds; core E2E paths, authorization, uploads, agent schema validation, and recovery behavior pass acceptance tests.

## Validation Strategy

- **Backend:** Pytest unit tests for services/repositories, API integration tests, migration tests, parser security/format tests, and graph-node contract tests.
- **Frontend:** component tests for key states, route-protection tests, and end-to-end tests for the onboarding-to-roadmap path.
- **AI/RAG:** fixed evaluation set covering roles, skills, citations, malformed model output, provider timeout, and weak-skill adaptation. Measure retrieval relevance and schema-valid response rate before changing prompts/models.
- **Release checks:** formatting, static types, dependency audit, secrets scan, migration upgrade, container build, and smoke tests.

## Explicit Non-Goals for This Phase

No application code, generated frontend, database migration, credential, fake student performance record, or cloud deployment has been created. This plan is intentionally the design baseline for the next implementation phase.
