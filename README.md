# Nisarg's TradeLab — FastAPI Backend

REST API for **Nisarg's TradeLab**, a trading journal platform. Handles accounts, trades, analytics, MetaTrader 5 sync, AI coaching, and CSV import/export.

This is the Python/FastAPI port of the original NestJS backend. It uses the **same PostgreSQL database** and **same API contract** (`/api/v1`, response shapes, auth) so the existing frontend and MT5 Expert Advisor work without changes.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Server | Uvicorn |
| Database | PostgreSQL ([Neon](https://neon.tech/)) |
| ORM | SQLAlchemy 2 (async) + asyncpg |
| Auth | [Clerk](https://clerk.com/) JWT |
| Validation | Pydantic v2 |
| AI | OpenAI (primary), Gemini (fallback) |
| File storage | Vercel Blob |
| Deployment | [FastAPI Cloud](https://fastapicloud.com/) |

---

## Features

- **Trading accounts** — CRUD, risk settings, instrument specs
- **Trades** — Manual entry, executions, close, reviews, tags/strategies/mistakes
- **Analytics** — 20+ endpoints (PnL, heatmaps, psychology, edge finder, etc.)
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
├── main.py                 # App entrypoint (FastAPI Cloud: app.main:app)
├── config.py               # Settings from environment
├── database.py             # Async SQLAlchemy engine/session
├── models/                 # SQLAlchemy models (22 tables)
├── schemas/                # Pydantic request/response models
├── routers/                # HTTP routes (/api/v1/...)
├── services/               # Business logic
├── calculators/            # Pure analytics, risk, and trade math
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

- **Python 3.11+**
- **PostgreSQL** (Neon recommended)
- **Clerk** account (same as frontend)
- Optional: OpenAI/Gemini keys, Vercel Blob token, MT5 secret

---

## Local setup

### 1. Clone and install

```bash
cd Nisarg-TradeLab-Backend-FastAPI

# With uv (recommended for FastAPI Cloud)
uv sync

# Or with pip
pip install -e .
```

### 2. Environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values. See [Environment variables](#environment-variables) below.

> **Never commit `.env`.** It is listed in `.gitignore`. Only `.env.example` (placeholders) belongs in git.

### 3. Run the server

```bash
# With uv
uv run uvicorn app.main:app --reload --port 3001

# Or directly
uvicorn app.main:app --reload --port 3001
```

### 4. Verify

- Root: http://localhost:3001/
- Health: http://localhost:3001/health
- OpenAPI docs: http://localhost:3001/docs

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Neon PostgreSQL connection string (pooled URL is fine) |
| `DIRECT_URL` | No | Direct Neon URL (optional; legacy from Prisma migrations) |
| `CLERK_SECRET_KEY` | Yes (prod) | Clerk secret key — same as frontend backend config |
| `FRONTEND_URL` | Yes | Allowed CORS origin(s), comma-separated |
| `NODE_ENV` | No | `development` \| `production` \| `test` (default: `development`) |
| `PORT` | No | Local port (default: `3001`) |
| `OPENAI_API_KEY` | For AI | OpenAI API key |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini` |
| `GEMINI_API_KEY` | No | Fallback LLM if OpenAI unavailable |
| `AI_COACH_ALLOWED_EMAILS` | No | Comma-separated emails; default allowlist in code if unset |
| `MT5_CONNECTION_TOKEN_SECRET` | Yes (prod) | HMAC secret for MT5 EA connection keys |
| `BLOB_READ_WRITE_TOKEN` | For uploads | Vercel Blob read/write token |

---

## API overview

All authenticated routes expect:

```http
Authorization: Bearer <clerk_jwt>
```

Success responses use `{ "data": ... }`. Errors use `{ "error": { "code", "message", "details?" } }`.

| Prefix | Description |
|--------|-------------|
| `GET /`, `GET /health` | Public — service info and health check |
| `/api/v1/users` | Current user profile |
| `/api/v1/accounts` | Trading accounts and risk settings |
| `/api/v1/accounts/{id}/instruments` | Per-account instrument specs |
| `/api/v1/trades` | Trade CRUD, executions, reviews |
| `/api/v1/trades/{id}/screenshots` | Chart screenshots |
| `/api/v1/analytics/*` | Portfolio analytics (20 endpoints) |
| `/api/v1/risk/*` | Risk calculator and instrument catalog |
| `/api/v1/strategies`, `/tags`, `/mistakes` | Taxonomy CRUD |
| `/api/v1/daily-journal` | Daily journal entries |
| `/api/v1/mt5/*` | MT5 connections (Clerk) + EA ingest (connection key) |
| `/api/v1/live-trades` | Open positions view |
| `/api/v1/import/*`, `/export/*` | CSV/JSON import and export |
| `/api/v1/ai/*` | AI Coach (allowlisted emails) |

Interactive API docs: `/docs` when the server is running.

---

## Authentication

### Frontend users (Clerk)

1. Frontend sends Clerk session JWT as `Authorization: Bearer ...`
2. Backend verifies token with Clerk
3. User is synced to local `users` table on first request (`/api/v1/users/me`)

### MetaTrader 5 EA

EA endpoints (`POST /api/v1/mt5/connect`, `/deals`, `/heartbeat`, etc.) use a **connection key**:

```http
Authorization: Bearer TJ_<base64url_key>
```

Keys are created via `POST /api/v1/mt5/connections` (Clerk auth). The raw key is shown once; only an HMAC hash is stored.

---

## Database

The schema matches the original Prisma/NestJS backend (22 tables). **No new migrations are required** if you point at an existing TradeLab Neon database.

SQLAlchemy models live in `app/models/`. The app uses the pooled `DATABASE_URL`; SQLAlchemy converts `postgresql://` to `postgresql+asyncpg://` automatically.

---

## Deploy to FastAPI Cloud

GitHub is **not required**. Deploy from your machine:

```bash
# One-time login
uv run fastapi login

# Deploy
uv run fastapi deploy
```

Then in the [FastAPI Cloud dashboard](https://fastapicloud.com):

1. Open your app → **Environment Variables**
2. **Import** your `.env` contents (or add variables manually)
3. Mark secrets (DB URL, Clerk, OpenAI, MT5, Blob) as **Secret**
4. Set `NODE_ENV=production` and production `FRONTEND_URL`
5. **Save and Redeploy**

Entrypoint is configured in `pyproject.toml`:

```toml
[tool.fastapi]
entrypoint = "app.main:app"
```

Update the frontend `NEXT_PUBLIC_API_BASE_URL` to your FastAPI Cloud URL after deploy.

---

## Frontend integration

Point the Next.js app at this backend:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:3001        # local
NEXT_PUBLIC_API_BASE_URL=https://your-app.fastapicloud.dev  # production
```

CORS allows origins listed in `FRONTEND_URL`.

---

## Development notes

- **Calculators** in `app/calculators/` are pure functions — easy to test and match NestJS behavior.
- **Rate limiting** is in-memory (per process); sufficient for Hobby/single-instance deploys.
- **AI Coach** is gated by `AI_COACH_ALLOWED_EMAILS` in addition to normal Clerk auth.
- **Errors** mirror the NestJS format for frontend compatibility.

---

## Related repos

- **Frontend** — `Nisarg-TradeLab-Frontend` (Next.js + Clerk)
- **Legacy backend** — `Nisarg-TradeLab-Backend` (NestJS; can be retired after FastAPI Cloud cutover)

---

## License

Private — UNLICENSED
