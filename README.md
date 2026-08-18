# Interview Coach

An AI-powered interview screening tool. A FastAPI backend drives a LangGraph agent that generates
screening questions from a job description then produces a pass/fail decision and a constructive feedback.

- **Prompt caching** — messages that get reused across multiple LLM calls within a run (like the job
  description and the compiled answers) are marked cacheable, so the model doesn't have to reprocess them
  from scratch each time.
- **Short-term memory** — each interview's progress is checkpointed as it goes, so an in-progress interview
  can resume across separate requests (and even a server restart) without losing state.
- **Long-term memory** — completed attempts are persisted per user and job description. When a user
  practices the same questions again, the feedback and decider agents are given the prior attempt so they
  can judge improvement rather than scoring in isolation.

## Setup

```bash
# 1. Start Postgres
docker compose up -d

# 2. Install dependencies
uv sync

# 3. Run the API
uv run fastapi dev backend/main.py
```

### Standalone CLI

Run the screening agent directly against a hardcoded job description, without the API or Postgres:

```bash
uv run python -m agents.screening_agent
```
