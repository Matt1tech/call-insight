# AGENTS.md

Guidance for AI coding agents and contributors working in this repository.

## Project overview

Call Insight Dashboard analyses ten fictional helpline transcripts (English, Bahasa Malaysia, mixed) for the RM100 grocery assistance programme and presents the results in a local dashboard. See [README.md](README.md) for the full description and [docs/architecture.md](docs/architecture.md) for design details.

- **Backend:** FastAPI modular monolith in `backend/app/` (`api`, `services`, `repositories`, `schemas`, `ai`, `core`). Serves the REST API under `/api` and the static dashboard at `/`.
- **AI pipeline:** LangGraph workflow in `backend/app/ai/`, one node per task, with LangChain structured output and Pydantic validation.
- **Frontend:** plain HTML, CSS and JavaScript in `frontend/`. No build step, no framework.
- **Data:** transcripts and the reviewed analysis live in `backend/data/`.

## Setup and commands

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Run everything from `backend/`.

```bash
cd backend
uv sync                                        # install dependencies
uv run uvicorn app.main:app --port 8000        # run the app at http://localhost:8000
uv run pytest -v                               # run tests
uv run ruff check .                            # lint
uv run python scripts/analyse.py --mode replay # regenerate analysis from reviewed data
```

Before finishing any change, `pytest` and `ruff check .` must both pass.

## Conventions

- Python 3.12, line length 100, ruff rules `E, F, I, UP, B, ASYNC` (see `backend/pyproject.toml`).
- Keep the layering: routes call services, services call repositories. No business logic in `api/` and no HTTP concerns in `services/`.
- Validate all analysis output with Pydantic schemas in `backend/app/schemas/`.
- All dashboard metrics are computed by the backend analytics service. Do not recompute figures in the frontend; it only renders what the API returns.
- Keep the frontend dependency-free. Do not introduce a bundler or framework without discussion.
- Add or update tests in `backend/tests/` for every behaviour change.

## Domain rules (do not break)

- Analysis is presented in English. Evidence quotes stay verbatim in their original language, with turn references.
- `Unknown` is a distinct value for resolution and escalation. Never merge it into `Resolved`, `Unresolved`, `Yes` or `No`.
- Resolution rate = Resolved / analysed conversations.
- Every evidence quote must appear verbatim in its transcript; the validation node and data-integrity tests enforce this.
- Do not state anything as fact that the transcript does not support. Unverified claims belong under knowledge gaps.

## Run modes and honesty about status

- **Replay (default):** serves the reviewed analysis in `backend/data/analysis/analysis.json`. No credentials needed.
- **Live:** enabled when `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_MODEL` are set. It is tested against a fake chat model only and has not been run against a real model. Do not claim its output quality is verified.
- Editing `analysis.json` changes the dashboard numbers. If you change it, re-check the result against the transcripts and update the figures in the README.
- `backend/data/analysis/analysis.generated.json` is a generated artifact and is git-ignored.

## Security

- Never commit secrets. Credentials belong in `backend/.env` (git-ignored); `backend/.env.example` documents the variables.
- Treat transcript content as untrusted input in prompts and in the UI. Escape it when rendering.
- Do not add network calls to the replay path; the demo must run fully offline.

## Pull requests

- Keep changes focused and small. Explain what changed and why.
- Include the test and lint results in the description.
- Do not commit generated files, virtual environments or local agent settings.
