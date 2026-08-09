"""
Agent orchestration layer.

    Coordinator agent  -> routes a request to the right subagent
    Profile / Skill gap / Roadmap / Question / Interview / Progress agents
        -> each wraps existing business logic from main.py, unchanged
    Feedback agent     -> every subagent's result passes through here
        before it goes back to the caller (e.g. the student dashboard)

Every agent still reads/writes the same SQLite tables via main.db() —
this file only adds a routing + feedback layer on top, it doesn't
change any existing behaviour or table schema.
"""
from __future__ import annotations

import json
import random
import time

# These names already exist on `main` by the time this module is imported
# (main.py imports `agents` only after defining them — see bottom of main.py).
from main import (
    db,
    get_user_track,
    TRACK_DATA,
    compute_skill_gap,
    ensure_roadmap_seeded,
)


# ---------------------------------------------------------------------------
# Feedback agent
# ---------------------------------------------------------------------------
class FeedbackAgent:
    """Doesn't own any data — looks at what a subagent produced and adds a
    short coaching note before the result goes back to the dashboard."""

    name = "feedback"

    def review(self, agent_name: str, uid: int, result: dict) -> dict:
        if "error" in result:
            return result
        note = self._note_for(agent_name, result)
        if note:
            result["feedback"] = note
        result["reviewed_by"] = self.name
        return result

    def _note_for(self, agent_name: str, result: dict) -> str:
        if agent_name == "profile":
            return "Profile saved — the skill gap agent will use this next." if result.get("status") == "saved" else ""

        if agent_name == "skillgap":
            missing = result.get("missing_skills") or []
            if missing:
                top = missing[0]
                top_name = top.get("name") if isinstance(top, dict) else top
                return f"Focus on {top_name} next — it closes the biggest gap for your track."
            return "No major skill gaps detected for your track right now."

        if agent_name == "roadmap":
            all_tasks = [t for tasks in (result.get("weeks") or {}).values() for t in tasks]
            total = len(all_tasks) or 1
            done = sum(1 for t in all_tasks if t.get("done"))
            return f"You're {round(100 * done / total)}% through the roadmap — keep the daily streak going."

        if agent_name == "question" and "correct" in result:
            return "Nice — that's correct." if result["correct"] else "Not quite — review that topic before the next question."

        if agent_name == "interview" and "rating" in result:
            return result.get("interview_feedback", "")

        if agent_name == "progress":
            pct = result.get("roadmap_completion", 0)
            if pct >= 75:
                return "Strong progress — you're on track for readiness."
            if pct >= 40:
                return "Steady progress — keep chipping away at the roadmap."
            return "Progress is early-stage — try to log a bit of roadmap time today."

        return ""


feedback_agent = FeedbackAgent()


# ---------------------------------------------------------------------------
# Subagents — thin wrappers around the logic that already lives in main.py.
# Same DB tables, same behaviour; just grouped behind a common
# .handle(uid, payload) interface so the Coordinator can dispatch uniformly.
# ---------------------------------------------------------------------------
class ProfileAgent:
    name = "profile"

    def handle(self, uid: int, payload: dict) -> dict:
        education_summary = payload.get("education_summary") or "; ".join(
            filter(None, [
                payload.get("highest_qualification"), payload.get("degree_branch"),
                payload.get("institution"), payload.get("graduation_year"),
            ])
        )
        conn = db()
        conn.execute(
            "UPDATE profiles SET education=?, skills=?, profile_done=1 WHERE user_id=?",
            (education_summary, payload.get("current_skills", ""), uid),
        )
        conn.commit()
        conn.close()
        return {"status": "saved"}


class SkillGapAgent:
    name = "skillgap"

    def handle(self, uid: int, payload: dict) -> dict:
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
        return {"track": track, "strong_skills": strong_skills, "missing_skills": missing_skills, "readiness": readiness}


class RoadmapAgent:
    name = "roadmap"

    def handle(self, uid: int, payload: dict) -> dict:
        ensure_roadmap_seeded(uid)
        conn = db()
        toggle_id = payload.get("toggle_task_id")
        if toggle_id is not None:
            row = conn.execute(
                "SELECT * FROM roadmap_tasks WHERE id=? AND user_id=?", (toggle_id, uid)
            ).fetchone()
            if not row:
                conn.close()
                return {"error": "Task not found"}
            conn.execute(
                "UPDATE roadmap_tasks SET done=? WHERE id=?",
                (1 if payload.get("done") else 0, toggle_id),
            )
            conn.commit()
        rows = conn.execute("SELECT * FROM roadmap_tasks WHERE user_id=? ORDER BY week, day", (uid,)).fetchall()
        conn.close()
        weeks: dict = {}
        for r in rows:
            weeks.setdefault(r["week"], []).append(dict(r))
        result = {"weeks": weeks}
        if toggle_id is not None:
            result["status"] = "updated"
        return result


class QuestionAgent:
    name = "question"

    def handle(self, uid: int, payload: dict) -> dict:
        track = get_user_track(uid)
        if payload.get("question_id") is not None and "selected_index" in payload:
            q = next((x for x in TRACK_DATA[track]["quiz_bank"] if x["id"] == payload["question_id"]), None)
            if not q:
                return {"error": "Question not found"}
            correct = payload["selected_index"] == q["answer"]
            conn = db()
            conn.execute(
                "INSERT INTO quiz_scores(user_id, correct, total, created_at) VALUES(?,?,?,?)",
                (uid, 1 if correct else 0, 1, time.time()),
            )
            conn.commit()
            conn.close()
            return {"correct": correct, "correct_index": q["answer"]}
        q = random.choice(TRACK_DATA[track]["quiz_bank"])
        return {"id": q["id"], "question": q["q"], "options": q["options"]}


class InterviewAgent:
    """New — was previously just a plain /api/interview route."""

    name = "interview"

    def handle(self, uid: int, payload: dict) -> dict:
        track = get_user_track(uid)
        if payload.get("question_id") is not None and "answer" in payload:
            length = len(payload["answer"].split())
            rating = min(5, max(1, round(length / 25) + 1))
            note = ("Good structure — add a concrete metric or outcome to strengthen it." if rating >= 3
                    else "Try the STAR format: situation, task, action, result.")
            conn = db()
            conn.execute(
                "INSERT INTO interview_scores(user_id, rating, feedback, created_at) VALUES(?,?,?,?)",
                (uid, rating, note, time.time()),
            )
            conn.commit()
            conn.close()
            return {"rating": rating, "interview_feedback": note}
        q = random.choice(TRACK_DATA[track]["interview_bank"])
        return {"id": q["id"], "question": q["q"]}


class ProgressAgent:
    """New — was previously just a plain /api/progress route."""

    name = "progress"

    def handle(self, uid: int, payload: dict) -> dict:
        conn = db()
        quiz = conn.execute(
            "SELECT correct, total, created_at FROM quiz_scores WHERE user_id=? ORDER BY created_at", (uid,)
        ).fetchall()
        interviews = conn.execute(
            "SELECT rating, created_at FROM interview_scores WHERE user_id=? ORDER BY created_at", (uid,)
        ).fetchall()
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


# ---------------------------------------------------------------------------
# Coordinator agent — single entry point. Looks up the right subagent,
# runs it, then routes the result through the Feedback agent.
# ---------------------------------------------------------------------------
class CoordinatorAgent:
    """New — orchestrates handoffs to the subagents below."""

    def __init__(self):
        self._agents = {
            "profile": ProfileAgent(),
            "skillgap": SkillGapAgent(),
            "roadmap": RoadmapAgent(),
            "question": QuestionAgent(),
            "interview": InterviewAgent(),
            "progress": ProgressAgent(),
        }

    def dispatch(self, agent_name: str, uid: int, payload: dict) -> dict:
        agent = self._agents.get(agent_name)
        if agent is None:
            return {"error": f"Unknown agent '{agent_name}'", "available": sorted(self._agents.keys())}
        result = agent.handle(uid, payload or {})
        return feedback_agent.review(agent_name, uid, result)


coordinator = CoordinatorAgent()
