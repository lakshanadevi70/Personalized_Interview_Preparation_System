# Personalized_Interview_Preparation_System
Multi-agent AI architecture for personalized student career guidance — a Coordinator Agent routes requests to specialized agents (Profile, Skill Gap, Roadmap, Question, Mock Interview, Progress) that merge into unified feedback on a student dashboard.

# 🎯 Multi-Agent AI Career Guidance System

A modular, multi-agent architecture that gives students personalized career guidance by routing each request to the specialized AI agent(s) that actually need to handle it — instead of running every capability on every query.

## 🧠 Overview

Traditional career guidance tools are generic. This system uses a **Coordinator Agent** to intelligently decide which specialist agents should respond to a student's request, then merges their outputs into a single, clear answer via a **Feedback Agent**.

```
Student → Web/Mobile UI → Coordinator Agent
                              ├── Profile Agent
                              ├── Skill Gap Agent
                              ├── Roadmap Agent
                              ├── Question Agent
                              ├── Mock Interview Agent
                              └── Progress Agent
                                     ↓
                              Feedback Agent → Student Dashboard
```

## ⚙️ How It Works

1. **Student** sends a request through the UI (e.g., *"Am I ready to be a backend developer?"*)
2. **Coordinator Agent** reads the intent and decides which specialist agents are relevant — skipping the rest to save cost and latency
3. Each triggered agent independently processes its part:
   - **Profile Agent** — builds/reads the student's skill profile
   - **Skill Gap Agent** — compares current skills against the target role
   - **Roadmap Agent** — generates a personalized learning path
   - **Question Agent** — generates practice questions on weak areas
   - **Mock Interview Agent** — simulates interview practice
   - **Progress Agent** — tracks completion and growth over time
4. **Feedback Agent** synthesizes all triggered outputs into one coherent response
5. Result is displayed on the **Student Dashboard**

## 🏗️ Architecture Highlights

- **Modular** — each agent is an independent, testable unit
- **Cost-efficient** — only relevant agents run per request
- **Extensible** — new agents can be added without touching existing ones
- **Orchestration-ready** — designed to map cleanly onto LangGraph's `StateGraph` (router node → conditional edges → agent nodes → merge node)

## 🛠️ Tech Stack (suggested)

| Layer | Options |
|---|---|
| LLM backbone | Claude / GPT-4 / Gemini API |
| Orchestration | LangGraph / LangChain / Claude Agent SDK |
| Backend | Python (FastAPI) |
| Frontend | React / Web-Mobile UI |
| Storage | PostgreSQL / Firebase |

## 📌 Example Flow

**Request:** *"Am I ready to be a backend developer?"*

**Coordinator triggers:** Profile Agent → Skill Gap Agent → Roadmap Agent
*(Question, Mock Interview, and Progress Agents stay idle — not relevant to this request)*

**Feedback Agent output:**
> "You're 60% ready for backend roles. Missing: SQL optimization, system design. Here's a 4-week roadmap."

## 🚀 Roadmap

- [ ] Build Coordinator Agent (intent classification + routing)
- [ ] Implement Profile Agent
- [ ] Implement Skill Gap Agent
- [ ] Implement Roadmap Agent
- [ ] Implement Question Agent
- [ ] Implement Mock Interview Agent
- [ ] Implement Progress Agent
- [ ] Build Feedback Agent (synthesis layer)
- [ ] Connect to Student Dashboard UI

## 📄 License

MIT
