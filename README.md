# Career Mentor

An AI-flavored career mentorship platform that takes a student through onboarding, resume analysis, skill-gap detection, a personalized learning roadmap, quizzes, and mock interviews — all coordinated through a lightweight multi-agent backend.

![Career Mentor architecture](./architecture/architecture.png)

## How it works

A single **Coordinator agent** sits in front of six specialist agents. Every request from the frontend is routed through the coordinator to the right specialist, and every specialist's result is passed through a **Feedback agent** before it reaches the student dashboard — so the student always gets a short coaching note alongside raw data, not just numbers.

| Agent | Responsibility |
|---|---|
| **Coordinator** | Routes each request to the correct specialist agent |
| **Profile agent** | Builds and stores the student's skill profile from onboarding + resume data |
| **Skill gap agent** | Compares the profile against the student's target role/track |
| **Roadmap agent** | Generates and tracks a week-by-week learning path |
| **Question agent** | Serves quiz questions and grades answers to probe weak spots |
| **Interview agent** | Runs simulated mock-interview Q&A and scores responses |
| **Progress agent** | Aggregates roadmap completion, quiz, and interview history |
| **Feedback agent** | Reviews every agent's output and attaches a short coaching note |

All agents read and write the same SQLite database — the agent layer is a routing + feedback layer on top of existing business logic, not a separate data store.

> Note: the current implementation uses this SQLite-backed agent-routing layer rather than the LangGraph/FAISS orchestration and React frontend shown as the target architecture in the diagram above — those are the intended next steps of the system.

## Project structure

```
career-mentor/
├── backend/
│   ├── main.py           # FastAPI app: auth, onboarding, resume parsing, all /api routes, SQLite schema
│   ├── agents.py         # Coordinator + specialist agents + feedback agent
│   └── requirements.txt
└── frontend/
    ├── index.html         # Landing page
    ├── login.html         # Auth (register/login)
    ├── dashboard.html     # Student dashboard (feedback-annotated summary)
    ├── career.html        # Career/track overview
    ├── skillgap.html      # Skill gap agent view
    ├── roadmap.html       # Roadmap agent view
    ├── courses.html       # Recommended courses
    ├── projects.html      # Recommended projects
    ├── quiz.html          # Question agent view
    ├── interview.html     # Mock interview agent view
    ├── progress.html      # Progress agent view
    ├── resume.html        # Resume upload/analysis
    ├── profile.html       # Student profile
    ├── settings.html      # Track/settings
    └── assets/
        ├── api.js         # Fetch wrapper for backend calls
        ├── auth.js        # Token storage/helpers
        ├── app.js         # Shared app logic
        ├── shell.js        # Shared page shell/nav
        └── style.css
```

## Backend API

**Auth & onboarding**
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET  /api/me`
- `GET  /api/onboarding/status`
- `POST /api/onboarding/profile`
- `POST /api/onboarding/resume`
- `POST /api/onboarding/resume/skip`

**Core features**
- `GET  /api/dashboard`
- `GET  /api/career`
- `GET  /api/skillgap`
- `GET  /api/roadmap`
- `GET  /api/courses`
- `GET  /api/projects`
- `GET  /api/quiz/next`
- `POST /api/quiz/answer`
- `GET  /api/interview/next`
- `POST /api/interview/answer`
- `GET  /api/progress`
- `GET  /api/settings`
- `POST /api/settings/track`

**Generic agent dispatch**
- `POST /api/agent/{agent_name}` — routes directly through the Coordinator to any of `profile`, `skillgap`, `roadmap`, `question`, `interview`, `progress`, with the result reviewed by the Feedback agent before it's returned.

Auth uses a simple HMAC-signed bearer token (`Authorization: Bearer <token>`) — no external auth dependency.

## Running locally

**Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
This creates `career_mentor.db` (SQLite) on first run and serves the API at `http://localhost:8000`.

**Frontend**
The frontend is static HTML/JS. Serve it with any static server and point `assets/api.js` at your backend URL, e.g.:
```bash
cd frontend
python -m http.server 5500
```
Then open `http://localhost:5500/index.html`.

## Tech stack

- **Backend:** FastAPI, SQLite (WAL mode), pypdf + python-docx for resume parsing, HMAC-signed tokens
- **Frontend:** Static HTML/CSS/JS (no build step)
- **Agent layer:** Coordinator/specialist/feedback pattern in `agents.py`, dispatched via `/api/agent/{agent_name}`
