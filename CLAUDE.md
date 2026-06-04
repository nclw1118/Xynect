# Xynect Project Context

Xynect is an AI-powered construction material supply chain MVP.

Current stable committed features:
- Next.js frontend
- FastAPI backend
- PostgreSQL via docker-compose
- DB models/migrations/supplier seed
- One-file upload flow
- Processing page
- Deterministic Excel/CSV extraction
- Editable review/extraction table
- Supplier recommendation flow
- Recommendation page grouped by tag

Important constraints:
- MVP is windows-first.
- No authentication.
- One file per session.
- Excel/CSV extraction is deterministic and must not use LLM.
- PDF/image OpenAI extraction is WIP and may be unstable.
- Do not refactor unrelated code.
- Current soft-release goal: workspace UI inspired by Panel AI, with left agent panel and right tabbed workspace.

Soft-release UI target:
- New /workspace/[sessionId] page.
- Left panel shows processing/extraction steps and Coming Soon placeholders for upload/model/chat.
- Right panel has tabs: Extraction Result and Recommendation.
- Extraction Result tab has Windows enabled, Doors/Walls Coming Soon.
- Users can edit window rows and add missing windows manually.
- Recommendation tab regenerates based on latest extraction data.
- Export CSV and PDF report via browser print/save-as-PDF.