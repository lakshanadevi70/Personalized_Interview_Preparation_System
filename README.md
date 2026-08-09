# Career Mentor — full stack

## Run
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

Open **http://localhost:8000** in your browser — the backend serves the
frontend directly from that same address.

### ⚠️ Most common mistake
Do **not** open the files in `frontend/` directly by double-clicking them
(a `file://...dashboard.html` URL). The pages fetch data from `/api/...`,
which only resolves when the page is loaded from the running backend's
own address (`http://localhost:8000/...`). Opened as a local file, every
API call silently fails — that's why the dashboard shows no resume score
and courses/projects show no links. As of this build, a failed page load
now shows a red banner explaining this instead of failing silently.

Checklist if a page looks empty:
1. Is `uvicorn` actually running in a terminal (no errors in that terminal)?
2. Is the browser URL `http://localhost:8000/...`, not a `file://` path?
3. Did you log in / register, then upload a resume on `resume.html`
   (or click "Skip") before expecting a resume score?

## Frontend structure
The frontend is a real multi-page site — each screen is its own HTML file that
navigates via normal browser page loads (not a client-side SPA router):

- `login.html` — sign in / register (entry point)
- `resume.html` — onboarding step 1 (resume upload/skip)
- `profile.html` — onboarding step 2 (profile wizard)
- `dashboard.html`, `career.html`, `skillgap.html`, `roadmap.html`,
  `courses.html`, `projects.html`, `quiz.html`, `interview.html`,
  `progress.html`, `settings.html` — the main app, linked via a shared sidebar
- `index.html` — root redirect: sends signed-in users into the app at the
  right onboarding step, everyone else to `login.html`

Shared code lives in `frontend/assets/`:
- `style.css` — all styling
- `api.js` — token storage + authenticated `fetch` wrapper (`api()`)
- `shell.js` — renders the sidebar/topbar shell and small view helpers
- `app.js` — data-loading logic for each app-shell page (dashboard, career, etc.)
- `auth.js` — login/register, resume upload, and profile-wizard logic

Every protected page (everything except `login.html`) starts with a tiny inline
guard script in `<head>` that redirects to `login.html` immediately if there's
no auth token in `localStorage`, so there's no flash of protected content for
signed-out visitors.

## Career tracks (role-based content)
Users pick a track at registration — **Tech**, **Design**, or **Marketing** —
and can change it later from Settings. The backend's `TRACK_DATA` drives
different career recommendations, skill gaps, courses, projects, quiz banks,
interview questions, and roadmap seeds per track (see `get_user_track()` in
`backend/main.py`), so the same set of pages shows different content per role
without any page-level branching.

## What's real
- FastAPI + SQLite backend (career_mentor.db auto-created)
- Real auth (register/login, signed tokens stored in localStorage)
- Real onboarding: profile answers and resume "parse" persist per user
- Real roadmap: 30-day task list seeded per user, checkboxes toggle in DB and update dashboard readiness live
- Real quiz + mock interview: questions served from backend, answers scored and stored, feed the Progress page
- Dashboard/skill-gap/progress numbers are computed from actual DB state, not hardcoded

## Mocked (clearly marked in code)
- Resume parsing returns a fixed skill list — swap in pdfplumber/pymupdf extraction in `/api/onboarding/resume`
- Career recommendation scores and course/project catalogs are static — wire to your LangGraph agents by replacing those route bodies
- Interview feedback is a simple length heuristic — replace with your interview agent's LLM call
