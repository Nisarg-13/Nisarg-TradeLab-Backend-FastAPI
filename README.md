# Nisarg's TradeLab — FastAPI Backend

REST API for the trading journal platform: accounts, trades, analytics, MT5 sync, AI coaching, and import/export.

**Backend repository:** https://github.com/Nisarg-13/Nisarg-TradeLab-Backend-FastAPI  
**Frontend repository:** https://github.com/Nisarg-13/Nisarg-TradeLab-Frontend

**Security:** See [SECURITY.md](./SECURITY.md) for vulnerability reporting and secret-handling guidelines.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Framework | FastAPI |
| Server | Uvicorn |
| Database | PostgreSQL (Neon) |
| ORM | SQLAlchemy 2 (async) + asyncpg |
| Auth | Clerk JWT |
| Validation | Pydantic v2 |
| AI | OpenAI (primary), Gemini (fallback) |
| File storage | Vercel Blob |
| Deployment | FastAPI Cloud |

---

## Features

- **Trading accounts** — CRUD, risk settings, instrument specs
- **Trades** — Manual entry, executions, close, reviews, tags/strategies/mistakes
- **Analytics** — PnL, heatmaps, psychology, edge finder, and more
- **Risk calculator** — Position sizing and rule violations
- **MT5 sync** — EA pushes deals, positions, and events via connection keys
- **Live trades** — Open positions with floating PnL
- **Daily journal** — Per-day notes and plans
- **Import / export** — CSV and JSON
- **Screenshots** — Trade chart uploads (Vercel Blob)
- **AI Coach** — Analysis and chat (email allowlist)

---

## Project structure

```
app/
├── main.py                 # Entrypoint (FastAPI Cloud: app.main:app)
├── config.py               # Settings from environment
├── database.py             # Async SQLAlchemy engine/session
├── models/                 # SQLAlchemy models
├── schemas/                # Pydantic request/response models
├── routers/                # HTTP routes (/api/v1/...)
├── services/               # Business logic
├── calculators/            # Analytics, risk, and trade math
│   ├── analytics/
│   ├── risk/
│   └── trades/
├── dependencies/           # Auth, DB session, rate limits
├── middleware/             # Exception handlers
├── utils/                  # CORS, MT5 keys, CSV parsing, etc.
└── data/                   # Default instrument catalog
```

---

## Prerequisites

- Python 3.11+
- PostgreSQL database (Neon)
- Clerk account (same as frontend)
- Optional: OpenAI/Gemini keys, Vercel Blob token, MT5 secret

---

## Local setup

```bash
cp .env.example .env
pip install -e .          # or: uv sync
uvicorn app.main:app --reload --port 3001
```

Verify:

- `GET /` — service info
- `GET /health` — health check
- `GET /docs` — OpenAPI docs

Do not commit `.env` (see `.gitignore`).

**macOS + Neon:** If you see `SSL: CERTIFICATE_VERIFY_FAILED`, ensure dependencies are installed (`pip install -e .`). The app uses the `certifi` CA bundle for PostgreSQL SSL. You can also run Python's **Install Certificates.command** (in your Python 3.x folder).

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `DIRECT_URL` | No | Direct DB URL (optional) |
| `CLERK_SECRET_KEY` | Yes (prod) | Clerk secret key |
| `FRONTEND_URL` | Yes | CORS allowed origin(s), comma-separated |
| `NODE_ENV` | No | `development` \| `production` \| `test` |
| `PORT` | No | Default: `3001` |
| `OPENAI_API_KEY` | For AI | OpenAI API key |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini` |
| `GEMINI_API_KEY` | No | Fallback LLM |
| `AI_COACH_ALLOWED_EMAILS` | No | Comma-separated emails allowed to use AI Coach (empty = disabled) |
| `MT5_CONNECTION_TOKEN_SECRET` | Yes (prod) | HMAC secret for MT5 connection keys |
| `BLOB_READ_WRITE_TOKEN` | For uploads | Vercel Blob token |

Full list with placeholders: `.env.example`

---

## API overview

Authenticated routes:

```http
Authorization: Bearer <clerk_jwt>
```

Responses: `{ "data": ... }` · Errors: `{ "error": { "code", "message" } }`

| Prefix | Description |
|--------|-------------|
| `GET /`, `GET /health` | Public |
| `/api/v1/users` | Current user |
| `/api/v1/accounts` | Trading accounts, risk settings |
| `/api/v1/accounts/{id}/instruments` | Instrument specs |
| `/api/v1/trades` | Trades, executions, reviews |
| `/api/v1/trades/{id}/screenshots` | Screenshots |
| `/api/v1/analytics/*` | Analytics |
| `/api/v1/risk/*` | Risk calculator |
| `/api/v1/strategies`, `/tags`, `/mistakes` | Taxonomy |
| `/api/v1/daily-journal` | Daily journal |
| `/api/v1/mt5/*` | MT5 connections + EA ingest |
| `/api/v1/live-trades` | Open positions |
| `/api/v1/import/*`, `/export/*` | CSV/JSON |
| `/api/v1/ai/*` | AI Coach |

---

## Authentication

**Clerk (frontend)** — Bearer JWT verified on each request. User synced on `GET /api/v1/users/me`.

**MT5 EA** — Bearer connection key (`TJ_...`) on EA endpoints (`/api/v1/mt5/connect`, `/deals`, `/heartbeat`, etc.). Keys created via `POST /api/v1/mt5/connections`; only a hash is stored.

---

## Database

PostgreSQL via SQLAlchemy. Models in `app/models/`. Uses pooled `DATABASE_URL` (`postgresql+asyncpg`).

Point at an existing TradeLab database — no new migrations required for cutover.

---

## Deploy to FastAPI Cloud

```bash
uv run fastapi login
uv run fastapi deploy
```

1. Import env vars in the dashboard (mark secrets as Secret)
2. Set `NODE_ENV=production` and production `FRONTEND_URL`
3. Save and redeploy

Entrypoint in `pyproject.toml`: `app.main:app`

---

## Frontend integration

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:3001
```

Production: set to your FastAPI Cloud URL, e.g.:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-backend.example.com
```

CORS uses `FRONTEND_URL`. The browser also proxies via `/backend-proxy` on Vercel (see frontend `next.config.ts`).

---

## MT5 Expert Advisor

Source and setup guide: [`mt5/`](./mt5/)

1. Generate a connection key in TradeLab (**Accounts → MT5 Connection**).
2. Compile `mt5/TradingJournalSync.mq5` in MetaEditor.
3. Allow WebRequest for your FastAPI backend URL in MT5 options.
4. Attach the EA with **ApiBaseUrl** = same backend URL and **ConnectionKey** = your `TJ_...` key.

EA endpoints use Bearer auth with the connection key (not Clerk JWT).

---

## Development notes

- Calculators in `app/calculators/` are pure functions
- Rate limiting is in-memory (per process)
- AI Coach requires `AI_COACH_ALLOWED_EMAILS` plus Clerk auth
- Error format matches the existing frontend contract
