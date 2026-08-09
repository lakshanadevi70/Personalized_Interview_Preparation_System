import sqlite3, hashlib, hmac, base64, json, time, os, random, re, io
from fastapi import FastAPI, HTTPException, Header, Depends, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List

DB = os.path.join(os.path.dirname(__file__), "career_mentor.db")
SECRET = "career-mentor-dev-secret-change-me"

app = FastAPI(title="Career Mentor API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def db():
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        track TEXT DEFAULT 'tech',
        created_at REAL
    );
    CREATE TABLE IF NOT EXISTS profiles(
        user_id INTEGER PRIMARY KEY,
        education TEXT, skills TEXT, target_job TEXT, experience TEXT,
        projects TEXT, study_hours TEXT, salary TEXT, company TEXT,
        learning_style TEXT, timeline TEXT, english_level TEXT,
        resume_skills TEXT, resume_score INTEGER DEFAULT 0,
        resume_done INTEGER DEFAULT 0, profile_done INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS roadmap_tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, week INTEGER, day INTEGER, title TEXT, done INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS quiz_scores(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, correct INTEGER, total INTEGER, created_at REAL
    );
    CREATE TABLE IF NOT EXISTS interview_scores(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, rating INTEGER, feedback TEXT, created_at REAL
    );
    """)
    conn.commit()
    conn.close()


init_db()

# ---------- auth helpers (simple signed token, no external deps) ----------

def hash_pw(pw: str) -> str:
    return hashlib.sha256((SECRET + pw).encode()).hexdigest()

def make_token(user_id: int) -> str:
    payload = json.dumps({"uid": user_id, "ts": time.time()})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def verify_token(token: str) -> int:
    try:
        payload_b64, sig = token.split(".")
        expected = hmac.new(SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError()
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()))
        return payload["uid"]
    except Exception:
        raise HTTPException(401, "Invalid or expired token")

def current_user(authorization: Optional[str] = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    return verify_token(authorization.split(" ", 1)[1])


# ---------- schemas ----------

class RegisterIn(BaseModel):
    email: str
    password: str
    track: str = "tech"

class LoginIn(BaseModel):
    email: str
    password: str

class ProfileIn(BaseModel):
    highest_qualification: str = ""
    degree_branch: str = ""
    institution: str = ""
    graduation_year: str = ""
    current_skills: str = ""

class ResumeIn(BaseModel):
    filename: str = "resume.pdf"

class QuizAnswerIn(BaseModel):
    question_id: int
    selected_index: int

class InterviewAnswerIn(BaseModel):
    question_id: int
    answer: str

class TaskToggleIn(BaseModel):
    done: bool


# ---------- resume text extraction ----------

def extract_resume_text(filename: str, raw: bytes) -> str:
    name = filename.lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        if name.endswith(".docx"):
            import docx
            document = docx.Document(io.BytesIO(raw))
            return "\n".join(p.text for p in document.paragraphs)
        # .doc (legacy binary) and anything else: best-effort decode
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return raw.decode("utf-8", errors="ignore")


# ---------- auth routes ----------

@app.post("/api/auth/register")
def register(body: RegisterIn):
    track = body.track if body.track in TRACK_DATA else "tech"
    conn = db()
    try:
        cur = conn.execute(
            "INSERT INTO users(email, password_hash, track, created_at) VALUES(?,?,?,?)",
            (body.email, hash_pw(body.password), track, time.time()),
        )
        conn.commit()
        uid = cur.lastrowid
        conn.execute("INSERT INTO profiles(user_id) VALUES(?)", (uid,))
        # seed a 30-day roadmap tailored to the chosen track
        titles = TRACK_DATA[track]["roadmap_titles"]
        for week in range(1, 5):
            for day in range(1, 8):
                t = titles[(week + day) % len(titles)]
                conn.execute("INSERT INTO roadmap_tasks(user_id, week, day, title, done) VALUES(?,?,?,?,?)",
                             (uid, week, day, t, 1 if (week == 1 and day <= 5) else 0))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Email already registered")
    finally:
        conn.close()
    return {"token": make_token(uid), "user_id": uid}


@app.post("/api/auth/login")
def login(body: LoginIn):
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE email=?", (body.email,)).fetchone()
    conn.close()
    if not row or row["password_hash"] != hash_pw(body.password):
        raise HTTPException(401, "Invalid email or password")
    return {"token": make_token(row["id"]), "user_id": row["id"]}


@app.get("/api/me")
def me(uid: int = Depends(current_user)):
    conn = db()
    row = conn.execute("SELECT id, email, track FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(row)


@app.get("/api/onboarding/status")
def onboarding_status(uid: int = Depends(current_user)):
    conn = db()
    row = conn.execute("SELECT resume_done, profile_done FROM profiles WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    if not row:
        return {"resume_done": False, "profile_done": False}
    return {"resume_done": bool(row["resume_done"]), "profile_done": bool(row["profile_done"])}


# ---------- onboarding ----------

@app.post("/api/onboarding/profile")
def save_profile(body: ProfileIn, uid: int = Depends(current_user)):
    education_summary = f"{body.highest_qualification} in {body.degree_branch}, {body.institution} ({body.graduation_year})"
    conn = db()
    conn.execute("""UPDATE profiles SET education=?, skills=?, profile_done=1 WHERE user_id=?""",
        (education_summary, body.current_skills, uid))
    conn.commit()
    conn.close()
    return {"status": "saved"}


@app.post("/api/onboarding/resume/skip")
def skip_resume(uid: int = Depends(current_user)):
    conn = db()
    conn.execute("UPDATE profiles SET resume_skills=?, resume_score=?, resume_done=1 WHERE user_id=?",
                 (json.dumps([]), 0, uid))
    _reseed_roadmap_tasks(conn, uid, get_user_track(uid), [])
    conn.commit()
    conn.close()
    return {"skills": [], "resume_score": 0, "filename": "skipped"}


@app.post("/api/onboarding/resume")
def upload_resume(file: UploadFile = File(...), uid: int = Depends(current_user)):
    conn = db()
    raw = file.file.read()
    text = extract_resume_text(file.filename or "resume.pdf", raw)
    detected_skills = detect_skills(text)
    # score: base for having a parsable resume + weighted by breadth of matched skills
    if not text.strip():
        score = 20
    else:
        score = min(97, 35 + 6 * len(detected_skills))
    conn.execute("UPDATE profiles SET resume_skills=?, resume_score=?, resume_done=1 WHERE user_id=?",
                 (json.dumps(detected_skills), score, uid))
    _reseed_roadmap_tasks(conn, uid, get_user_track(uid), detected_skills)
    conn.commit()
    conn.close()
    return {"skills": detected_skills, "resume_score": score, "filename": file.filename}


# ---------- dashboard / career / skill gap (all track-aware) ----------

TRACKS = ["tech", "design", "marketing"]

TRACK_DATA = {
    "tech": {
        "label": "Tech",
        "strong_skills": ["Python", "React", "Machine Learning", "FastAPI"],
        "missing_skills": [
            {"name": "Docker", "priority": "High"},
            {"name": "System design", "priority": "High"},
            {"name": "SQL tuning", "priority": "Medium"},
        ],
        "recommendations": [
            {"role": "AI/ML Engineer", "score": 86,
             "why": "Your ML internships and LangGraph/FAISS project work map closely to entry-level ML engineering roles.",
             "skills": ["Python", "Machine Learning", "TensorFlow", "FastAPI"]},
            {"role": "Full-stack Developer", "score": 74,
             "why": "Django and React experience across internships supports full-stack roles at product companies.",
             "skills": ["React", "Django", "JavaScript"]},
            {"role": "Backend Developer", "score": 79,
             "why": "FastAPI and SQL work supports backend-focused roles building and scaling APIs.",
             "skills": ["FastAPI", "SQL", "System design"]},
            {"role": "Data Analyst", "score": 68,
             "why": "Python and SQL fundamentals transfer well into analytics-heavy roles.",
             "skills": ["Python", "SQL", "Pandas"]},
        ],
        "courses": [
            {"title": "Docker for Developers", "platform": "YouTube", "duration": "4h 20m", "free": True, "url": "https://www.youtube.com/results?search_query=docker+for+developers"},
            {"title": "System Design Primer", "platform": "Coursera", "duration": "6 weeks", "free": False, "url": "https://www.coursera.org/search?query=system%20design"},
            {"title": "SQL Performance Tuning", "platform": "Docs", "duration": "2h 10m", "free": True, "url": "https://use-the-index-luke.com/"},
        ],
        "projects": [
            {"title": "Containerized ML API", "level": "Intermediate", "outcome": "Ship a real model behind a real container boundary.", "url": "https://github.com/search?q=containerized+ml+api+fastapi+docker"},
            {"title": "Personal task tracker", "level": "Beginner", "outcome": "Learn CRUD end to end.", "url": "https://github.com/search?q=task+tracker+crud+starter"},
            {"title": "Distributed job queue", "level": "Advanced", "outcome": "Understand what scale actually means.", "url": "https://github.com/search?q=distributed+job+queue+python"},
        ],
        "roadmap_titles": ["Foundations refresh", "Core language deep-dive", "Build a small project",
                            "Docker basics", "System design intro", "Mock interview", "Review & consolidate"],
        "quiz_bank": [
            {"id": 1, "q": "Which Docker command builds an image from a Dockerfile?",
             "options": ["docker run", "docker build", "docker exec"], "answer": 1},
            {"id": 2, "q": "Which SQL clause filters rows before aggregation?",
             "options": ["HAVING", "WHERE", "ORDER BY"], "answer": 1},
            {"id": 3, "q": "In a REST API, which method is idempotent by convention?",
             "options": ["POST", "PUT", "PATCH"], "answer": 1},
        ],
        "interview_bank": [
            {"id": 1, "q": "Tell me about a time you debugged a production issue under time pressure."},
            {"id": 2, "q": "Walk me through how you'd design a URL shortener."},
            {"id": 3, "q": "Describe a project where you had to learn a new technology quickly."},
        ],
    },
    "design": {
        "label": "Design",
        "strong_skills": ["Figma", "Wireframing", "User research", "Prototyping"],
        "missing_skills": [
            {"name": "Design systems", "priority": "High"},
            {"name": "Accessibility (WCAG)", "priority": "High"},
            {"name": "Motion design", "priority": "Medium"},
        ],
        "recommendations": [
            {"role": "Product Designer", "score": 84,
             "why": "Your Figma and user research portfolio work maps closely to entry-level product design roles.",
             "skills": ["Figma", "User research", "Prototyping"]},
            {"role": "UX Researcher", "score": 71,
             "why": "Interview and usability-testing experience supports dedicated UX research tracks.",
             "skills": ["User research", "Usability testing", "Prototyping"]},
            {"role": "UI Designer", "score": 77,
             "why": "Strong Figma and prototyping skills map well to visual-focused UI roles.",
             "skills": ["Figma", "Prototyping"]},
        ],
        "courses": [
            {"title": "Design Systems 101", "platform": "YouTube", "duration": "3h 40m", "free": True, "url": "https://www.youtube.com/results?search_query=design+systems+101"},
            {"title": "Accessibility for Designers", "platform": "Coursera", "duration": "4 weeks", "free": False, "url": "https://www.coursera.org/search?query=accessibility%20design"},
            {"title": "Motion Design Basics", "platform": "Docs", "duration": "2h 00m", "free": True, "url": "https://www.smashingmagazine.com/category/motion-design/"},
        ],
        "projects": [
            {"title": "Redesign a checkout flow", "level": "Intermediate", "outcome": "Ship a case study with before/after metrics.", "url": "https://www.behance.net/search/projects?search=checkout+flow+redesign"},
            {"title": "Component library", "level": "Beginner", "outcome": "Learn design tokens and reusable components.", "url": "https://www.figma.com/community/search?resource_type=components&query=component%20library"},
            {"title": "End-to-end product design sprint", "level": "Advanced", "outcome": "Practice research through hi-fi prototype in one week.", "url": "https://www.behance.net/search/projects?search=design+sprint+case+study"},
        ],
        "roadmap_titles": ["Foundations refresh", "Design tool deep-dive", "Build a case study",
                            "Design systems basics", "Accessibility intro", "Portfolio review", "Review & consolidate"],
        "quiz_bank": [
            {"id": 1, "q": "What does WCAG primarily set standards for?",
             "options": ["Web accessibility", "Web speed", "Web hosting"], "answer": 0},
            {"id": 2, "q": "In Figma, what lets you build reusable UI elements?",
             "options": ["Frames", "Components", "Comments"], "answer": 1},
            {"id": 3, "q": "Which method is best for early-stage usability testing?",
             "options": ["A/B testing on production", "Moderated usability sessions", "Ad click-through rate"], "answer": 1},
        ],
        "interview_bank": [
            {"id": 1, "q": "Walk me through a design decision you made based on user research."},
            {"id": 2, "q": "How would you redesign the checkout flow for an e-commerce app?"},
            {"id": 3, "q": "Describe a time you had to defend a design choice to stakeholders."},
        ],
    },
    "marketing": {
        "label": "Marketing",
        "strong_skills": ["Content strategy", "SEO", "Analytics", "Copywriting"],
        "missing_skills": [
            {"name": "Paid media (PPC)", "priority": "High"},
            {"name": "Marketing automation", "priority": "High"},
            {"name": "A/B testing", "priority": "Medium"},
        ],
        "recommendations": [
            {"role": "Growth Marketer", "score": 80,
             "why": "Your SEO and analytics work maps closely to entry-level growth marketing roles.",
             "skills": ["SEO", "Analytics", "A/B testing"]},
            {"role": "Content Marketing Specialist", "score": 76,
             "why": "Copywriting and content strategy experience supports content-focused marketing roles.",
             "skills": ["Copywriting", "Content strategy"]},
            {"role": "SEO Specialist", "score": 73,
             "why": "Strong SEO fundamentals support dedicated organic-search roles.",
             "skills": ["SEO", "Analytics"]},
        ],
        "courses": [
            {"title": "PPC Fundamentals", "platform": "YouTube", "duration": "3h 10m", "free": True, "url": "https://www.youtube.com/results?search_query=ppc+fundamentals"},
            {"title": "Marketing Automation Deep Dive", "platform": "Coursera", "duration": "5 weeks", "free": False, "url": "https://www.coursera.org/search?query=marketing%20automation"},
            {"title": "A/B Testing for Marketers", "platform": "Docs", "duration": "1h 50m", "free": True, "url": "https://cxl.com/blog/ab-testing-guide/"},
        ],
        "projects": [
            {"title": "Run a small PPC campaign", "level": "Intermediate", "outcome": "Ship a campaign with real budget and CTR/CPA metrics.", "url": "https://ads.google.com/intl/en/getstarted/"},
            {"title": "SEO content calendar", "level": "Beginner", "outcome": "Learn keyword research and content planning.", "url": "https://ahrefs.com/blog/content-calendar/"},
            {"title": "Full-funnel growth experiment", "level": "Advanced", "outcome": "Design and run an A/B test end to end.", "url": "https://cxl.com/blog/ab-testing-guide/"},
        ],
        "roadmap_titles": ["Foundations refresh", "Channel deep-dive", "Build a campaign",
                            "Automation basics", "Analytics intro", "Campaign review", "Review & consolidate"],
        "quiz_bank": [
            {"id": 1, "q": "What does CTR stand for?",
             "options": ["Cost to reach", "Click-through rate", "Conversion tracking ratio"], "answer": 1},
            {"id": 2, "q": "Which metric best measures ad spend efficiency?",
             "options": ["CPA", "Impressions", "Bounce rate"], "answer": 0},
            {"id": 3, "q": "In A/B testing, what should differ between the two versions?",
             "options": ["Everything", "Only one variable", "The audience"], "answer": 1},
        ],
        "interview_bank": [
            {"id": 1, "q": "Tell me about a campaign you ran and how you measured its success."},
            {"id": 2, "q": "Walk me through how you'd grow organic traffic for a new product."},
            {"id": 3, "q": "Describe a time an experiment or campaign didn't work — what did you learn?"},
        ],
    },
}


# ---------- resume-driven skill detection & scoring ----------

# Every skill mentioned anywhere in TRACK_DATA (strong/missing/role skills), mapped
# to the text patterns we'll look for in a resume. Keeps detection in sync with the
# actual skill vocabulary used across all tracks instead of a separate hardcoded list.
def _collect_known_skills():
    names = set()
    for t in TRACK_DATA.values():
        names.update(t["strong_skills"])
        names.update(m["name"] for m in t["missing_skills"])
        for r in t["recommendations"]:
            names.update(r["skills"])
    return sorted(names)

SKILL_ALIASES = {
    "Machine Learning": ["machine learning", "scikit-learn", "sklearn", "tensorflow", "pytorch",
                          "keras", "deep learning", "neural network", "\\bml\\b"],
    "System design": ["system design", "distributed systems", "scalability", "high availability"],
    "SQL tuning": ["sql tuning", "query optimization", "query tuning", "indexing strategy"],
    "SQL": ["\\bsql\\b", "postgres", "postgresql", "mysql", "sqlite", "database design"],
    "Paid media (PPC)": ["\\bppc\\b", "paid media", "google ads", "meta ads", "paid search"],
    "Marketing automation": ["marketing automation", "hubspot", "mailchimp", "\\bautomation\\b"],
    "A/B testing": ["a/b test", "ab testing", "split test", "\\bab test\\b"],
    "Accessibility (WCAG)": ["\\bwcag\\b", "accessibility", "\\ba11y\\b"],
    "User research": ["user research", "usability testing", "user interviews"],
    "Design systems": ["design system", "design tokens"],
}

# Skills worth surfacing on the dashboard/skill-gap page even when they aren't tied
# to a specific role's "required skills" list (e.g. supporting ML/tooling skills).
# Kept separate from SKILL_ALIASES so it can grow freely without touching how role
# recommendations are scored.
EXTRA_SKILLS = {
    "Deep Learning": ["deep learning"],
    "NLP": ["\\bnlp\\b", "natural language processing"],
    "Computer Vision": ["computer vision", "\\bcv\\b(?!\\w)"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "Pandas": ["\\bpandas\\b"],
    "NumPy": ["\\bnumpy\\b"],
    "Data Visualization": ["data visualization", "tableau", "power bi"],
    "Git": ["\\bgit\\b", "github", "gitlab"],
    "AWS": ["\\baws\\b", "amazon web services"],
    "Azure": ["\\bazure\\b"],
    "GCP": ["\\bgcp\\b", "google cloud"],
    "Docker": ["\\bdocker\\b", "containeriz"],
    "Kubernetes": ["kubernetes", "\\bk8s\\b"],
    "CI/CD": ["ci/cd", "continuous integration", "continuous deployment"],
    "Java": ["\\bjava\\b(?!script)"],
    "JavaScript": ["javascript", "\\bjs\\b"],
    "TypeScript": ["typescript"],
    "Node.js": ["node\\.js", "\\bnodejs\\b", "\\bnode\\b"],
    "HTML/CSS": ["\\bhtml\\b", "\\bcss\\b"],
    "MongoDB": ["mongodb"],
    "REST APIs": ["rest api", "restful"],
    "Agile/Scrum": ["\\bagile\\b", "\\bscrum\\b"],
    "Adobe XD": ["adobe xd"],
    "Sketch": ["\\bsketch\\b"],
    "InVision": ["invision"],
    "Illustrator": ["illustrator"],
    "Photoshop": ["photoshop"],
    "Google Analytics": ["google analytics"],
    "Email Marketing": ["email marketing"],
    "Social Media Marketing": ["social media marketing", "social media strategy"],
}

def detect_skills(text: str) -> list:
    if not text:
        return []
    low = text.lower()
    found = []
    for skill in _collect_known_skills():
        patterns = SKILL_ALIASES.get(skill, [re.escape(skill.lower())])
        if any(re.search(p, low) for p in patterns):
            found.append(skill)
    for skill, patterns in EXTRA_SKILLS.items():
        if skill in found:
            continue
        if any(re.search(p, low) for p in patterns):
            found.append(skill)
    return found


def _all_roles():
    """Every recommended role across every track, tagged with its track."""
    roles = []
    for track_key, t in TRACK_DATA.items():
        for r in t["recommendations"]:
            roles.append({**r, "track": track_key, "track_label": t["label"]})
    return roles


def compute_resume_recommendations(resume_skills: list, fallback_track: str):
    """Score every role (across all tracks) by overlap with the skills actually
    detected on the user's resume, so the career page reflects what they uploaded
    rather than a static per-track list."""
    resume_set = set(resume_skills or [])
    if not resume_set:
        # no resume parsed yet — fall back to the static, track-based defaults
        return TRACK_DATA[fallback_track]["recommendations"]

    scored = []
    for role in _all_roles():
        req = set(role["skills"])
        matched = req & resume_set
        overlap = len(matched) / max(1, len(req))
        score = round(30 + 65 * overlap)
        if matched:
            why = f"Your resume shows {', '.join(sorted(matched))}, which lines up well with this role."
        else:
            why = role["why"]
        scored.append({**role, "score": score, "why": why, "matched_skills": sorted(matched)})

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:6]


def compute_skill_gap(resume_skills: list, track: str):
    """Strong/missing skills driven by the resume when one has been uploaded,
    falling back to the static track defaults otherwise. Gap is computed only
    against the user's own track's roles — cross-track roles (surfaced as
    bonus options on the Career page) are deliberately excluded here so the
    roadmap never asks a tech-track user to learn a design/marketing skill
    just because one keyword happened to overlap."""
    resume_set = set(resume_skills or [])
    data = TRACK_DATA[track]
    if not resume_set:
        return data["strong_skills"], data["missing_skills"]

    track_roles = [{**r, "track": track, "track_label": data["label"]} for r in data["recommendations"]]
    scored = []
    for role in track_roles:
        req = set(role["skills"])
        matched = req & resume_set
        overlap = len(matched) / max(1, len(req))
        score = round(30 + 65 * overlap)
        scored.append({**role, "score": score, "matched_skills": sorted(matched)})
    scored.sort(key=lambda r: r["score"], reverse=True)
    top_roles = scored[:3]

    gap_count = {}
    for i, role in enumerate(top_roles):
        for skill in role["skills"]:
            if skill not in resume_set:
                gap_count[skill] = gap_count.get(skill, 0) + (2 if i == 0 else 1)

    missing = [
        {"name": name, "priority": "High" if weight >= 2 else "Medium"}
        for name, weight in sorted(gap_count.items(), key=lambda kv: -kv[1])
    ][:5]
    return sorted(resume_set), missing


def build_roadmap_titles(missing_skills: list, track: str) -> list:
    """Turns the user's actual skill gap into a roadmap task list: an opening
    review, two tasks per missing skill (intro + hands-on practice, high-priority
    gaps first), then interview/project/consolidation tasks at the end. Falls
    back to the generic per-track titles when there's no resume-based gap yet."""
    if not missing_skills:
        return TRACK_DATA[track]["roadmap_titles"]
    ordered = sorted(missing_skills, key=lambda m: 0 if m.get("priority") == "High" else 1)
    middle = []
    for m in ordered:
        middle.append(f"{m['name']} — introduction")
        middle.append(f"{m['name']} — hands-on practice")
    opening = ["Foundations refresh", "Review your strongest skills"]
    closing = ["Build a project using your new skills", "Mock interview", "Review & consolidate"]
    return opening + middle + closing


def _reseed_roadmap_tasks(conn, uid: int, track: str, resume_skills: list):
    """Writes fresh roadmap rows using the given (already-open) connection —
    does NOT commit or close it. Caller is responsible for the transaction,
    so this always lands in the same commit as the profile update that
    triggered it (no partial/out-of-sync state between the two)."""
    _, missing_skills = compute_skill_gap(resume_skills, track)
    titles = build_roadmap_titles(missing_skills, track)
    conn.execute("DELETE FROM roadmap_tasks WHERE user_id=?", (uid,))
    for week in range(1, 5):
        for day in range(1, 8):
            t = titles[(week + day) % len(titles)]
            conn.execute("INSERT INTO roadmap_tasks(user_id, week, day, title, done) VALUES(?,?,?,?,?)",
                         (uid, week, day, t, 0))


def reseed_roadmap_from_gap(uid: int, track: str, resume_skills: list):
    """Standalone version (own connection + commit) for callers that aren't
    already inside a transaction."""
    conn = db()
    try:
        _reseed_roadmap_tasks(conn, uid, track, resume_skills)
        conn.commit()
    finally:
        conn.close()


def get_user_track(uid: int) -> str:
    conn = db()
    row = conn.execute("SELECT track FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    track = row["track"] if row and row["track"] in TRACK_DATA else "tech"
    return track


def ensure_roadmap_seeded(uid: int):
    """Self-heals accounts that ended up with zero roadmap tasks (e.g. created
    before seeding worked correctly, or an interrupted registration)."""
    conn = db()
    count = conn.execute("SELECT COUNT(*) c FROM roadmap_tasks WHERE user_id=?", (uid,)).fetchone()["c"]
    if count == 0:
        track = get_user_track(uid)
        titles = TRACK_DATA[track]["roadmap_titles"]
        for week in range(1, 5):
            for day in range(1, 8):
                t = titles[(week + day) % len(titles)]
                conn.execute("INSERT INTO roadmap_tasks(user_id, week, day, title, done) VALUES(?,?,?,?,?)",
                             (uid, week, day, t, 1 if (week == 1 and day <= 5) else 0))
        conn.commit()
    conn.close()


@app.get("/api/dashboard")
def dashboard(uid: int = Depends(current_user)):
    ensure_roadmap_seeded(uid)
    track = get_user_track(uid)
    data = TRACK_DATA[track]
    conn = db()
    profile = conn.execute("SELECT * FROM profiles WHERE user_id=?", (uid,)).fetchone()
    tasks = conn.execute("SELECT * FROM roadmap_tasks WHERE user_id=? ORDER BY week, day", (uid,)).fetchall()
    conn.close()
    total = len(tasks) or 1
    done = sum(1 for t in tasks if t["done"])
    readiness = round(30 + 60 * (done / total))
    resume_skills = json.loads(profile["resume_skills"]) if profile and profile["resume_skills"] else []
    _, missing_skills = compute_skill_gap(resume_skills, track)
    return {
        "track": track,
        "track_label": data["label"],
        "readiness": readiness,
        "resume_score": profile["resume_score"] if profile else 0,
        "missing_skills": missing_skills[:3],
        "roadmap_progress": {"done": done, "total": total},
        "upcoming_tasks": [dict(t) for t in tasks if not t["done"]][:4],
    }


@app.get("/api/career")
def career(uid: int = Depends(current_user)):
    track = get_user_track(uid)
    conn = db()
    profile = conn.execute("SELECT resume_skills, resume_done FROM profiles WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    resume_skills = json.loads(profile["resume_skills"]) if profile and profile["resume_skills"] else []
    recs = compute_resume_recommendations(resume_skills, track)
    return {
        "track": track,
        "resume_based": bool(resume_skills),
        "resume_skills": resume_skills,
        "recommendations": recs,
    }


@app.get("/api/skillgap")
def skillgap(uid: int = Depends(current_user)):
    ensure_roadmap_seeded(uid)
    track = get_user_track(uid)
    conn = db()
    profile = conn.execute("SELECT resume_skills FROM profiles WHERE user_id=?", (uid,)).fetchone()
    tasks = conn.execute("SELECT * FROM roadmap_tasks WHERE user_id=?", (uid,)).fetchall()
    conn.close()
    total = len(tasks) or 1
    done = sum(1 for t in tasks if t["done"])
    readiness = round(30 + 60 * (done / total))
    resume_skills = json.loads(profile["resume_skills"]) if profile and profile["resume_skills"] else []
    strong_skills, missing_skills = compute_skill_gap(resume_skills, track)
    return {
        "track": track,
        "resume_based": bool(resume_skills),
        "strong_skills": strong_skills,
        "missing_skills": missing_skills,
        "readiness": readiness,
    }


# ---------- roadmap ----------

@app.get("/api/roadmap")
def roadmap(uid: int = Depends(current_user)):
    ensure_roadmap_seeded(uid)
    conn = db()
    rows = conn.execute("SELECT * FROM roadmap_tasks WHERE user_id=? ORDER BY week, day", (uid,)).fetchall()
    conn.close()
    weeks = {}
    for r in rows:
        weeks.setdefault(r["week"], []).append(dict(r))
    return {"weeks": weeks}


@app.patch("/api/roadmap/task/{task_id}")
def toggle_task(task_id: int, body: TaskToggleIn, uid: int = Depends(current_user)):
    conn = db()
    row = conn.execute("SELECT * FROM roadmap_tasks WHERE id=? AND user_id=?", (task_id, uid)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Task not found")
    conn.execute("UPDATE roadmap_tasks SET done=? WHERE id=?", (1 if body.done else 0, task_id))
    conn.commit()
    conn.close()
    return {"status": "updated"}


# ---------- courses / projects (static catalog) ----------

@app.get("/api/courses")
def courses(uid: int = Depends(current_user)):
    track = get_user_track(uid)
    return {"track": track, "courses": TRACK_DATA[track]["courses"]}


@app.get("/api/projects")
def projects(uid: int = Depends(current_user)):
    track = get_user_track(uid)
    return {"track": track, "projects": TRACK_DATA[track]["projects"]}


# ---------- quiz ----------

@app.get("/api/quiz/next")
def quiz_next(uid: int = Depends(current_user)):
    track = get_user_track(uid)
    q = random.choice(TRACK_DATA[track]["quiz_bank"])
    return {"id": q["id"], "question": q["q"], "options": q["options"]}


@app.post("/api/quiz/answer")
def quiz_answer(body: QuizAnswerIn, uid: int = Depends(current_user)):
    track = get_user_track(uid)
    q = next((x for x in TRACK_DATA[track]["quiz_bank"] if x["id"] == body.question_id), None)
    if not q:
        raise HTTPException(404, "Question not found")
    correct = body.selected_index == q["answer"]
    conn = db()
    conn.execute("INSERT INTO quiz_scores(user_id, correct, total, created_at) VALUES(?,?,?,?)",
                 (uid, 1 if correct else 0, 1, time.time()))
    conn.commit()
    conn.close()
    return {"correct": correct, "correct_index": q["answer"]}


# ---------- mock interview ----------

@app.get("/api/interview/next")
def interview_next(uid: int = Depends(current_user)):
    track = get_user_track(uid)
    q = random.choice(TRACK_DATA[track]["interview_bank"])
    return {"id": q["id"], "question": q["q"]}


@app.post("/api/interview/answer")
def interview_answer(body: InterviewAnswerIn, uid: int = Depends(current_user)):
    length = len(body.answer.split())
    rating = min(5, max(1, round(length / 25) + 1))
    feedback = "Good structure — add a concrete metric or outcome to strengthen it." if rating >= 3 \
        else "Try the STAR format: situation, task, action, result."
    conn = db()
    conn.execute("INSERT INTO interview_scores(user_id, rating, feedback, created_at) VALUES(?,?,?,?)",
                 (uid, rating, feedback, time.time()))
    conn.commit()
    conn.close()
    return {"rating": rating, "feedback": feedback}


# ---------- progress ----------

@app.get("/api/progress")
def progress(uid: int = Depends(current_user)):
    conn = db()
    quiz = conn.execute("SELECT correct, total, created_at FROM quiz_scores WHERE user_id=? ORDER BY created_at", (uid,)).fetchall()
    interviews = conn.execute("SELECT rating, created_at FROM interview_scores WHERE user_id=? ORDER BY created_at", (uid,)).fetchall()
    tasks = conn.execute("SELECT done FROM roadmap_tasks WHERE user_id=?", (uid,)).fetchall()
    conn.close()
    total = len(tasks) or 1
    done = sum(1 for t in tasks if t["done"])
    streak = min(30, done)
    return {
        "streak_days": streak,
        "quiz_scores": [r["correct"] for r in quiz][-8:],
        "interview_scores": [r["rating"] for r in interviews][-8:],
        "roadmap_completion": round(100 * done / total),
    }


# ---------- settings ----------

class TrackIn(BaseModel):
    track: str

@app.get("/api/settings")
def get_settings(uid: int = Depends(current_user)):
    conn = db()
    row = conn.execute("SELECT email, track FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    result = dict(row)
    result["track_label"] = TRACK_DATA[result["track"]]["label"] if result["track"] in TRACK_DATA else result["track"]
    result["available_tracks"] = [{"value": k, "label": v["label"]} for k, v in TRACK_DATA.items()]
    return result


@app.post("/api/settings/track")
def set_track(body: TrackIn, uid: int = Depends(current_user)):
    if body.track not in TRACK_DATA:
        raise HTTPException(400, "Unknown track")
    conn = db()
    conn.execute("UPDATE users SET track=? WHERE id=?", (body.track, uid))
    conn.commit()
    conn.close()
    return {"status": "updated", "track": body.track}


# ---------- agent orchestration layer ----------
# Coordinator + Feedback agents, per the architecture diagram: every subagent
# (profile, skillgap, roadmap, question, interview, progress) is dispatched
# here and its result is routed through the Feedback agent before it comes
# back. All existing /api/* routes above are untouched and keep working —
# this is an additive layer, not a replacement.
from agents import coordinator


@app.post("/api/agent/{agent_name}")
def run_agent(agent_name: str, payload: dict = Body(default={}), uid: int = Depends(current_user)):
    result = coordinator.dispatch(agent_name, uid, payload)
    if "error" in result:
        status = 404 if "not found" in result["error"].lower() else 400
        raise HTTPException(status, result["error"])
    return result


# ---------- serve frontend ----------
# The frontend is now a set of real, separate HTML pages (login.html, resume.html,
# profile.html, dashboard.html, career.html, ...) that navigate via normal page loads
# instead of client-side view-switching. StaticFiles(html=True) serves each file at
# its own path (e.g. GET /dashboard.html) and serves index.html for "/".
# This mount is registered last so it never shadows the /api/* routes above.

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
