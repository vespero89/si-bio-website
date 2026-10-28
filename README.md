# sito-sibio

Website of Si Bio (wine and olive oil, Offida). Light FastAPI + Jinja2 + HTMX app, no database,
no admin panel: content lives in files under `content/`.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --reload-dir app   # http://127.0.0.1:8000
```

Optional environment variables (or a `.env` file, never committed): `BASE_URL`.

## Checks

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -q
```

Rules for contributors are in `.claude/CLAUDE.md`.
