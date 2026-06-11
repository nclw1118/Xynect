# Xynect

AI-powered construction material supply chain MVP. Upload a construction document, extract window schedules, review and correct the data, and receive ranked supplier/pricing recommendations.

## Prerequisites

- Docker + Docker Compose
- Python 3.11+ (`/opt/homebrew/bin/python3.11`)
- Node.js 18+

## Quick start

### 1. Start PostgreSQL

```bash
docker compose up -d
```

Postgres will be available at `localhost:5432` (user: `xynect`, password: `xynect_password`, db: `xynect_mvp`).

### 2. Set up environment

```bash
cp .env.example .env
```

Edit `.env` if needed. Default values run the full app in stub mode (no API key required).

### 3. Start the backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check: http://localhost:8000/api/health

API docs: http://localhost:8000/docs

### 4. Run database migrations

Run once after first setup, and again after any schema change:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

Check current migration state:

```bash
alembic current
```

### 5. Seed fake suppliers

Run once (idempotent — safe to re-run):

```bash
cd backend
source .venv/bin/activate
python -m app.seed.suppliers
```

### 6. Verify database connectivity

```bash
cd backend
source .venv/bin/activate
python -m app.core.database
```

Prints `Database connection OK` if Postgres is reachable.

### 7. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000

## LLM modes

| `LLM_PROVIDER` | `OPENAI_API_KEY` | Behavior |
|---|---|---|
| `stub` | not required | PDF/image extraction returns safe mock data. Excel/CSV uses real deterministic parsing. Full flow works. |
| `openai` | required | PDF/image extraction uses GPT-4.1 vision. Missing values returned as blank/null — never invented. |

Set `LLM_PROVIDER=stub` in `.env` for local development.

## File limits

- Max upload size: 75 MB
- Accepted types: PDF, JPG, JPEG, PNG, XLSX, XLS, CSV
- One file per session

## Project structure

```
backend/        FastAPI + Python
frontend/       Next.js + TypeScript + Tailwind + shadcn/ui
storage/        Uploaded files (gitignored)
docker-compose.yml
.env.example
```

## Local ngrok + OpenAI soft-release demo

This is the fastest path for a trusted one-user demo. Everything runs on your laptop; ngrok provides public HTTPS URLs. No cloud deployment required.

### What you need

- ngrok installed (`brew install ngrok`)
- An OpenAI API key
- Your laptop awake and plugged in

### Step 1 — Keep your laptop awake

Run this in a dedicated terminal before you start:

```bash
caffeinate -dimsu
```

Leave it running for the duration of the demo. `Ctrl-C` to stop when done.

### Step 2 — Start PostgreSQL

```bash
docker compose up -d
```

### Step 3 — Configure .env for OpenAI mode

Edit `.env` (copy from `.env.example` if you haven't already):

```
DATABASE_URL=postgresql://xynect:xynect_password@localhost:5432/xynect_mvp

LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4.1

# Fill in after step 7 below
FRONTEND_URL=https://PLACEHOLDER.ngrok-free.app
```

> **Important:** `FRONTEND_URL` must be the frontend ngrok URL for CORS to work. You will fill it in after step 7. Leave it as a placeholder for now and restart the backend in step 8.

Do not commit `.env` — it contains your API key.

### Step 4 — Run migrations and seed suppliers (once)

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
python -m app.seed.suppliers
```

### Step 5 — Start the backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Step 6 — Start the backend ngrok tunnel

Open a new terminal:

```bash
ngrok http 8000
```

Copy the `https://...ngrok-free.app` URL shown. This is your **backend URL**.

### Step 7 — Configure the frontend to use the backend ngrok URL

Create or edit `frontend/.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=https://YOUR-BACKEND.ngrok-free.app
```

> `NEXT_PUBLIC_API_BASE_URL` is baked in at Next.js dev startup, not just build time. You must set this before `npm run dev`.

### Step 8 — Start the frontend

```bash
cd frontend
npm run dev
```

### Step 9 — Start the frontend ngrok tunnel

Open a new terminal:

```bash
ngrok http 3000
```

Copy the `https://...ngrok-free.app` URL shown. This is your **frontend URL** — the link you will share.

### Step 10 — Update FRONTEND_URL and restart the backend

1. Edit `.env`, replace the `FRONTEND_URL` placeholder with the frontend ngrok URL from step 9:
   ```
   FRONTEND_URL=https://YOUR-FRONTEND.ngrok-free.app
   ```
2. Stop the backend (`Ctrl-C` in the backend terminal) and restart it:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Step 11 — Share the frontend URL

Send your user the frontend ngrok URL (`https://YOUR-FRONTEND.ngrok-free.app`). That is the only URL they need.

### Terminals to keep open

| Terminal | Process |
|---|---|
| 1 | `caffeinate -dimsu` |
| 2 | `docker compose up -d` (can close after DB starts) |
| 3 | `uvicorn app.main:app --reload --port 8000` |
| 4 | `ngrok http 8000` (backend tunnel) |
| 5 | `npm run dev` |
| 6 | `ngrok http 3000` (frontend tunnel) |

### Demo tips

- **Best demo input:** a single-page PDF window schedule or a JPG/PNG image of a window schedule. OpenAI vision extracts tags, dimensions, and NFRC values.
- **Fallback:** if OpenAI extraction produces unexpected results, upload a CSV or XLSX file instead — deterministic extraction always works and needs no API key.
- **Supported file types:** PDF, JPG, JPEG, PNG, XLSX, XLS, CSV (max 75 MB).
- **If ngrok URLs change:** ngrok generates new URLs each time it restarts unless you have a reserved domain. If you restart ngrok mid-demo, you must update `FRONTEND_URL` in `.env`, restart the backend, update `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local`, and restart the frontend.

### Notes

- This is not a production deployment. Sessions and uploaded files live only on your laptop.
- Uploaded files are stored in `storage/uploads/` (gitignored). They persist on your laptop until you delete them. Backend restarts do not automatically delete uploaded files.
- Session data (extracted rows, recommendations) is in your local PostgreSQL container and persists across backend restarts.
- The ngrok free tier shows a browser interstitial the first time a new user visits. They can click "Visit Site" to proceed.

---

## Deploying to Render (or any hosted environment)

### Backend environment variables

Set these in your Render backend service before deploying:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Your hosted PostgreSQL connection string |
| `FRONTEND_URL` | Your deployed frontend URL (e.g. `https://xynect.onrender.com`) — used for CORS |
| `LLM_PROVIDER` | `stub` for soft release (no API key required) |
| `UPLOAD_DIR` | `./storage/uploads` (default — see storage note below) |

**`FRONTEND_URL` is required for CORS.** If not set, only `http://localhost:3000` is allowed, which means all browser requests from the deployed frontend will be blocked.

### Frontend environment variables

`NEXT_PUBLIC_API_BASE_URL` is baked into the Next.js bundle **at build time**. Set it in your Render frontend service environment variables before the build runs:

```
NEXT_PUBLIC_API_BASE_URL=https://your-backend-url.onrender.com
```

If you forget to set this, the frontend will try to call `http://localhost:8000` from the user's browser and all API requests will fail silently.

### Database setup (run once after first deploy)

These one-off commands must be run before the first request:

```bash
# 1. Apply database schema
alembic upgrade head

# 2. Insert fake suppliers
python -m app.seed.suppliers
```

On Render, run these as one-off jobs from the Render dashboard (Shell tab or a one-off job).

### File storage on Render

Uploaded files are stored at `./storage/uploads/` on the local filesystem. **Render's filesystem is ephemeral** — files are deleted on every redeploy.

For the soft-release demo:
- This is acceptable as long as you do not redeploy between uploading a file and generating recommendations.
- The database session data (extracted rows, recommendations) persists in PostgreSQL and survives restarts.

For production: replace local storage with S3 or an equivalent object store.

### Render cold start

Free-tier Render services sleep after inactivity. The first request after sleep can take 30–60 seconds. The workspace's left panel polling will continue retrying during this window.
