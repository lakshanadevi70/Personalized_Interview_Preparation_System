# Personalised Interview Preparation System

A multi-agent system that prepares candidates for interviews through an iterative loop of mock interviews, evaluation, and personalized coaching — with a **handoff architecture** where each agent passes its output, context, and state to the next agent best suited to continue the task.

## How it works

A **Planner agent** sits at the center as the master orchestrator. It analyzes the candidate's resume and profile up front, decides whether they're ready for a mock interview or need groundwork first, and routes them accordingly. From there, control moves between specialist agents, each reading and writing to a **shared memory** store so no context is lost across handoffs.

| Agent | Responsibility |
|---|---|
| **Planner** | Analyzes resume/profile, estimates interview readiness, routes to Interviewer or Coach — the master agent that rules over the whole workflow |
| **Interviewer** | Conducts adaptive mock interviews; generates questions by role, profile, difficulty, and interview type (Technical / HR / Behavioral); only collects responses, doesn't grade them |
| **Evaluator** | Independently scores responses on technical correctness, communication clarity, problem-solving, confidence, completeness, and depth; produces a performance report |
| **Coach** | Turns the evaluation into a personalized study roadmap — topic prioritization, resources, practice questions, revision strategy, confidence-building — then hands the candidate back to the Interviewer |

This creates a closed learning loop: **Planner → Interviewer → Evaluator → Coach → Interviewer → ...** — each pass through the loop should raise the candidate's readiness.

## Handoff architecture

**Handoff** is the process of transferring a task, along with its necessary context and state, from one agent to another specialized agent so the most suitable agent can continue and complete the task efficiently.

Two kinds of transfer happen between agents:
- **Control flow / agent handoff** — which agent acts next
- **Data / context read-write** — what each agent reads from and writes back to shared memory

```
                     USER
                      │
                      ▼
              ┌───────────────┐
      ┌──────▶│ PLANNER AGENT │◀──────┐
      │       └───────────────┘       │
 ready for                       needs
 interview?                   preparation?
      │                              │
      ▼                              ▼
┌─────────────────┐         ┌───────────────────────┐
│ INTERVIEWER      │         │ PRE-INTERVIEW PREP    │
│ AGENT            │         │ COACH                 │
└─────────────────┘         └───────────────────────┘
      │                              │
      ▼                              │
┌─────────────────┐                  │
│ EVALUATOR AGENT  │                  │
└─────────────────┘                  │
      │                              │
      ▼                              │
┌───────────────────────┐            │
│ POST-INTERVIEW PREP    │◀───────────┘
│ COACH                  │
└───────────────────────┘
      │
      ▼
┌─────────────┐
│ SHARED      │◀── all agents read/write context here
│ MEMORY      │
└─────────────┘
```

## Agent workflow in detail

**1. Planner Agent (Orchestrator)**
Analyzes the candidate's resume, profile, preferred role, years of experience, technical skills, and any extra context to build an initial profile and estimate interview readiness. If the candidate shows sufficient foundational knowledge, control passes directly to the Interviewer; if there are significant gaps, control routes to the Coach first. The Planner maintains context across every downstream agent.

**2. Interviewer Agent**
Conducts the actual interview session, dynamically generating questions based on job role, candidate profile, prior performance, difficulty level, and interview type. It deliberately does not grade answers — that responsibility stays with the Evaluator — and hands the conversation/response history off once a response is collected.

**3. Evaluator Agent**
Scores the candidate's responses independently of the Interviewer across technical correctness, communication clarity, problem-solving ability, confidence, completeness, and depth of understanding, then forwards the resulting performance report to the Coach.

**4. Coach Agent**
Uses the evaluation report to identify weak concepts and build a personalized roadmap: topic prioritization, resource recommendations, practice questions, a revision strategy, and confidence-building suggestions. After sufficient preparation, it hands the candidate back to the Interviewer, continuing the loop.

## Tools / functions

| Function | Purpose |
|---|---|
| `call_llm()` | Common LLM interface used by all agents to send prompts and receive responses |
| `get_hf_client()` | Establishes the connection to the Hugging Face inference service |
| `run_resume_analyzer()` | Extracts and structures candidate information from the uploaded resume |
| `run_role_analyzer()` | Converts the target job description into structured role requirements and competencies |
| `run_planner()` | Master Planner — determines candidate readiness and routes to the right workflow |
| `run_coach()` | Concept Coach — technical explanations, doubt resolution, guided learning |
| `run_intent_detector()` | Detects candidate intent during the interview and controls the system's next action |
| `run_interviewer()` | Conducts an adaptive, role-specific mock interview and generates contextual questions |
| `run_evaluator()` | Evaluates interview performance, assigns scores, identifies weaknesses, produces skill-gap data |
| `run_roadmap_generator()` | Creates an adaptive 8-week preparation roadmap from profile, target role, skill gaps, and evaluation results |

## Design notes

- **Separation of responsibilities**: the Interviewer never grades, and the Evaluator never asks questions — each agent owns one concern.
- **Shared memory** is what makes the handoffs cheap: instead of re-explaining context on every transfer, agents read/write to a common store the Planner (and every other agent) can consult.
- **Readiness-based routing** means not every candidate goes through the same path — the Planner can skip straight to interviewing for well-prepared candidates or insert a coaching pass first for others.
- **The Coach → Interviewer loop** is what makes this a *preparation system* rather than a one-shot mock interview tool — each cycle should measurably close skill gaps identified in the previous evaluation.
