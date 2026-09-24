"""The whole RAG pipeline: extract -> chunk -> embed -> retrieve -> generate."""
import io
import re
import zlib

import numpy as np
from django.conf import settings
from django.db import transaction

from .models import Chunk, Document

SYSTEM_PROMPT = (
    "You answer questions using only the numbered context passages provided. "
    "Cite the passages you rely on with bracketed numbers like [1] or [2][3]. "
    "If the passages don't contain the answer, say you couldn't find it in the "
    "documents instead of guessing. Be concise and direct."
)


# ---------- ingestion ----------
def extract_segments(upload):
    """Return a list of (page_number | None, text)."""
    name = upload.name.lower()
    data = upload.read()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    if name.endswith(".docx"):
        import docx

        doc = docx.Document(io.BytesIO(data))
        return [(None, "\n".join(p.text for p in doc.paragraphs))]
    if name.endswith((".txt", ".md")):
        return [(None, data.decode("utf-8", errors="ignore"))]
    raise ValueError("Unsupported file type. Upload a PDF, DOCX, TXT or MD file.")


def chunk_text(text, size=1000, overlap=150):
    text = " ".join(text.split())
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind(". ", start + size // 2, end)
            if cut != -1:
                end = cut + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


STOP = set("a an and are as at be by can do does for from has have how i if in is it its many much my of on or our need that the this to was were what when where which who will with you".split())


def _real(key):
    """True for a real key (not empty, not the '.env.example' placeholder)."""
    return bool(key) and "..." not in key


def has_llm():
    return _real(settings.ANTHROPIC_API_KEY) or _real(settings.OPENAI_API_KEY)


def local_embed(texts, dim=1024):
    """Free offline fallback: hashed words + word pairs. No API key needed."""
    out = np.zeros((len(texts), dim), dtype=np.float32)
    for i, t in enumerate(texts):
        words = [w[:6] for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP]  # crude stemming
        for tok in words + [f"{a}_{b}" for a, b in zip(words, words[1:])]:
            out[i, zlib.crc32(tok.encode()) % dim] += 1
    out = np.log1p(out)
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return out / norms


def offline_answer(sources):
    lines = ["No AI key is set, so here are the most relevant passages from your documents:", ""]
    lines += [f"- {x['excerpt'][:220].strip()}… [{x['id']}]" for x in sources[:3]]
    lines += ["", "Add `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` to `backend/.env` to get written answers."]
    return "\n".join(lines)


def embed(texts):
    """Return an (n, d) float32 array of L2-normalised embeddings."""
    if not _real(settings.OPENAI_API_KEY):
        return local_embed(texts)
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    vectors = []
    for i in range(0, len(texts), 96):
        resp = client.embeddings.create(model=settings.EMBEDDING_MODEL, input=texts[i : i + 96])
        vectors.extend(d.embedding for d in resp.data)
    arr = np.array(vectors, dtype=np.float32)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


@transaction.atomic
def ingest(user, upload):
    pieces = [(page, c) for page, text in extract_segments(upload) for c in chunk_text(text)]
    if not pieces:
        raise ValueError("No readable text found. Scanned PDFs need OCR before uploading.")
    if len(pieces) > settings.MAX_CHUNKS_PER_DOC:
        raise ValueError("This document is too long. Try one under about 150 pages.")
    vectors = embed([c for _, c in pieces])
    doc = Document.objects.create(owner=user, title=upload.name[:255], chunk_count=len(pieces))
    Chunk.objects.bulk_create(
        Chunk(document=doc, index=i, page=page, text=text, embedding=vectors[i].tobytes())
        for i, (page, text) in enumerate(pieces)
    )
    return doc


# ---------- retrieval + generation ----------
def retrieve(user, question, document_ids=None, k=None):
    qs = Chunk.objects.filter(document__owner=user).select_related("document")
    if document_ids:
        qs = qs.filter(document_id__in=document_ids)
    chunks = list(qs)
    if not chunks:
        return []
    q = embed([question])[0]
    chunks = [c for c in chunks if len(c.embedding) == q.nbytes]  # same embedding type only
    if not chunks:
        return []
    matrix = np.vstack([np.frombuffer(c.embedding, dtype=np.float32) for c in chunks])
    scores = matrix @ q
    top = np.argsort(scores)[::-1][: k or settings.TOP_K]
    return [(chunks[i], float(scores[i])) for i in top]


def generate(system, messages):
    if _real(settings.ANTHROPIC_API_KEY):
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=settings.ANTHROPIC_MODEL, max_tokens=1024, system=system, messages=messages
        )
        return resp.content[0].text
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=settings.OPENAI_CHAT_MODEL,
        messages=[{"role": "system", "content": system}, *messages],
    )
    return resp.choices[0].message.content


def clean_history(history):
    msgs = [
        {"role": m["role"], "content": m["content"][:2000]}
        for m in (history or [])[-6:]
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
    ]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    return msgs


def stream_generate(system, messages):
    """Yield the answer as it is generated."""
    if _real(settings.ANTHROPIC_API_KEY):
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        with client.messages.stream(
            model=settings.ANTHROPIC_MODEL, max_tokens=1024, system=system, messages=messages
        ) as stream:
            yield from stream.text_stream
        return
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    stream = client.chat.completions.create(
        model=settings.OPENAI_CHAT_MODEL,
        stream=True,
        messages=[{"role": "system", "content": system}, *messages],
    )
    for event in stream:
        if event.choices and event.choices[0].delta.content:
            yield event.choices[0].delta.content


def prepare(user, question, document_ids=None, history=None):
    """Retrieve passages and build the LLM messages. Returns (messages, sources)."""
    hits = retrieve(user, question, document_ids)
    if not hits:
        return None, []
    context = "\n\n".join(
        f"[{n}] ({c.document.title}{f', page {c.page}' if c.page else ''})\n{c.text}"
        for n, (c, _) in enumerate(hits, 1)
    )
    messages = clean_history(history) + [
        {"role": "user", "content": f"Context passages:\n{context}\n\nQuestion: {question}"}
    ]
    sources = [
        {
            "id": n,
            "document_id": c.document_id,
            "document": c.document.title,
            "page": c.page,
            "excerpt": c.text[:600],
            "score": round(score, 3),
        }
        for n, (c, score) in enumerate(hits, 1)
    ]
    return messages, sources


def answer(user, question, document_ids=None, history=None):
    messages, sources = prepare(user, question, document_ids, history)
    if not messages:
        return {"answer": "There's nothing to search yet. Upload a document first.", "sources": []}
    if not has_llm():
        return {"answer": offline_answer(sources), "sources": sources}
    return {"answer": generate(SYSTEM_PROMPT, messages), "sources": sources}
