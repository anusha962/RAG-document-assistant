# Marginalia: RAG Document Assistant

Upload PDF, Word, TXT or Markdown files and ask questions about them. Answers are grounded in your documents and cite the exact passages (with page numbers for PDFs).

**Stack:** Django + Django REST Framework · React (Vite) · PostgreSQL · OpenAI embeddings · Claude or OpenAI for answers

## Highlights

- **Streaming answers** over server-sent events (Django `StreamingHttpResponse` to a `fetch` stream reader), with a stop button.
- **Verifiable citations**: every `[n]` in an answer is clickable and opens the exact source passage, highlighted, with page number and match score.
- **Multi-user and private**: token auth, per-user document isolation, per-scope rate limits.
- **Provider-agnostic generation**: Claude or OpenAI behind one function; embeddings via OpenAI.
- **Tested and automated**: Django test suite (AI calls mocked) and a GitHub Actions CI that also builds the frontend.
- **One-click deploy**: Render Blueprint provisions Postgres, the API and the static site.

## How it works

1. **Ingest** – text is extracted (`pypdf`, `python-docx`), split into ~1000-character overlapping chunks, embedded, and stored in the database.
2. **Retrieve** – the question is embedded and compared to your chunks by cosine similarity (NumPy); the top 5 are selected.
3. **Generate** – the passages and question go to the LLM, which must answer only from them and cite `[n]`.

All RAG logic lives in `backend/documents/rag.py`. Each user sees only their own documents.

## Quick start (Windows)

Install Python (tick "Add python.exe to PATH") and Node.js LTS, then in PowerShell inside this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1   # one time
powershell -ExecutionPolicy Bypass -File .\run.ps1     # every time
```

The app opens at http://localhost:5173. It works **without any API key** (it shows the most relevant passages). For written answers, put `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `backend/.env` and restart. Try it with `sample-docs/Northwind_Employee_Handbook.pdf`. Locally the database is SQLite and needs no setup; on Render it is PostgreSQL.

## Run locally (manual, Mac/Linux)

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add OPENAI_API_KEY
python manage.py migrate
python manage.py runserver    # http://localhost:8000

# frontend (new terminal)
cd frontend
cp .env.example .env
npm install
npm run dev                   # http://localhost:5173
```

Run backend tests: `python manage.py test` (AI calls are mocked).

## Push to GitHub

```bash
git init && git add . && git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/rag-document-assistant.git
git push -u origin main
```

## Deploy on Render

1. In Render: **New > Blueprint**, connect the GitHub repo. It reads `render.yaml` and creates a Postgres database, the API (`rag-backend`) and the React site (`rag-frontend`).
2. When prompted, enter `OPENAI_API_KEY` (and optionally `ANTHROPIC_API_KEY`). Leave `FRONTEND_URL` and `VITE_API_URL` blank for now. Apply.
3. Once both services exist, copy their URLs:
   - `rag-backend` > Environment > `FRONTEND_URL` = `https://<your-frontend>.onrender.com`
   - `rag-frontend` > Environment > `VITE_API_URL` = `https://<your-backend>.onrender.com`
4. Redeploy `rag-frontend` (Vite bakes the URL in at build time) and the backend will restart on its own.

If a service name is already taken on Render, rename it in `render.yaml`.

## Environment variables (backend)

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Required. Embeddings, and answers if no Anthropic key |
| `ANTHROPIC_API_KEY` | Optional. Answers with Claude (`ANTHROPIC_MODEL`, default `claude-sonnet-5`) |
| `FRONTEND_URL` | Allowed CORS origin(s), comma-separated |
| `SECRET_KEY`, `DATABASE_URL` | Generated/provided by Render |

## Good to know

- Render's free web service sleeps when idle (first request takes ~30–60 s) and free Postgres expires after 30 days. Upgrade the plans for anything permanent.
- Registration is open. Rate limits (`config/settings.py`) cap chat, upload and login attempts to protect your API bill.
- Similarity search loads a user's chunks into memory, which is fine for thousands of chunks. For much larger libraries, switch to `pgvector` (Render Postgres supports it).
- Scanned PDFs have no text layer and are rejected with a message; run OCR first.
