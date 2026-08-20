# TradingJournalSync EA

Expert Advisor that syncs your MT5 account with Nisarg's TradeLab (read-only).

## Before you start

1. In TradeLab: **Accounts** → select account → **Generate connection key** → copy the `TJ_...` key.
2. Note your backend URL (e.g. `https://nisarg-tradelab-backend-fastapi-72bd27e6.fastapicloud.dev` — no trailing slash).
3. Ensure `MT5_CONNECTION_TOKEN_SECRET` is set on FastAPI Cloud (same value used when the key was created).

## Compile `.mq5` → `.ex5`

`.ex5` is the compiled binary MT5 runs. You must compile locally:

1. Open **MetaTrader 5**.
2. **File → Open Data Folder**.
3. Copy `TradingJournalSync.mq5` into `MQL5/Experts/`.
4. In MT5: **Tools → MetaQuotes Language Editor (MetaEditor)**.
5. Open `Experts/TradingJournalSync.mq5`.
6. Press **Compile** (F7). You should get `0 error(s)`.
7. The compiled file appears as `MQL5/Experts/TradingJournalSync.ex5`.

Alternatively: in MT5 **Navigator → Expert Advisors**, right-click the EA → **Compile**.

## Allow WebRequest (required)

1. MT5 → **Tools → Options → Expert Advisors**.
2. Enable **Allow algorithmic trading**.
3. Enable **Allow WebRequest for listed URL**.
4. Add your backend host, e.g.:
   ```text
   https://nisarg-tradelab-backend-fastapi-72bd27e6.fastapicloud.dev
   ```
5. Click **OK** and restart MT5 if prompted.

## Attach the EA

1. Open any chart (e.g. EURUSD M15).
2. **Navigator → Expert Advisors → TradingJournalSync** → drag onto the chart.
3. Inputs:
   - **ApiBaseUrl** — your FastAPI backend URL (no trailing slash)
   - **ConnectionKey** — your `TJ_...` key from TradeLab
   - **SyncIntervalSeconds** — default `1` (live position updates every second)
   - **HistoryDays** — default `90` (initial deal import window)
4. Enable **Allow Algo Trading** (toolbar button).
5. Check the **Experts** tab for `TradeLab: connected` and sync messages.

## Verify in TradeLab

**Accounts → MT5 Connection** should show:

- Status: **CONNECTED**
- MT5 login + server filled in
- Live data: **LIVE** (after first position sync)
- Last sync: recent timestamp

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `HTTP 1003` on `/mt5/deals` | Request timed out during historical import — redeploy backend + recompile EA v1.2.0; live prices sync independently |
| Live prices blank / STALE | Check Experts log for `open position sync ok`; if missing, deal import was blocking sync in older EA versions |
| `WebRequest failed (4014)` or `(4060)` | Enable **Allow WebRequest for listed URL** and add backend URL; restart MT5 |
| `WebRequest failed` | Add backend URL to allowed WebRequest list |
| `401 Unauthorized` | Wrong or revoked connection key; regenerate in TradeLab |
| `4060` / URL not allowed | Same as WebRequest allowlist |
| Status stays DISCONNECTED | Check Experts log; confirm backend is live (`/health`) |
| Key lost | Revoke + generate new key in TradeLab; update EA inputs |

## What the EA syncs

- Account pairing (`/mt5/connect`)
- Heartbeat (`/mt5/heartbeat`)
- Balance/equity (`/mt5/account`)
- Instrument specs (`/mt5/instruments`)
- Historical deals in chunks (`/mt5/deals`)
- Open position snapshots (`/mt5/positions`)
- New deals on trade activity (`OnTradeTransaction`)

TradeLab never receives your MT5 password.
