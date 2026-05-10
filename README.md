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
