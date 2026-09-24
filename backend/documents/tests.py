import zlib
from unittest.mock import patch

import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from . import rag


def fake_embed(texts):
    out = np.zeros((len(texts), 64), dtype=np.float32)
    for i, t in enumerate(texts):
        for w in t.lower().split():
            out[i, zlib.crc32(w.encode()) % 64] += 1
    return out / np.linalg.norm(out, axis=1, keepdims=True)


def fake_generate(system, messages):
    return "Paris is the capital [1]."


class ChunkTests(APITestCase):
    def test_chunking_makes_progress_and_overlaps(self):
        chunks = rag.chunk_text("word " * 1000)
        self.assertGreater(len(chunks), 3)
        self.assertTrue(all(len(c) <= 1000 for c in chunks))


@patch("documents.rag.embed", fake_embed)
@patch("documents.rag.generate", fake_generate)
class ApiFlowTests(APITestCase):
    def register(self, name):
        r = self.client.post("/api/auth/register/", {"username": name, "password": "s3cret-pass!"})
        self.assertEqual(r.status_code, 201)
        return r.json()["token"]

    def test_upload_chat_and_isolation(self):
        token = self.register("alice")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        f = SimpleUploadedFile("notes.txt", b"Paris is the capital of France. Berlin is in Germany.")
        r = self.client.post("/api/documents/", {"file": f}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)

        self.assertEqual(len(self.client.get("/api/documents/").json()), 1)
        r = self.client.post("/api/chat/", {"question": "What is the capital of France?"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["sources"][0]["document"], "notes.txt")

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.register('bob')}")
        self.assertEqual(self.client.get("/api/documents/").json(), [])

    def test_rejects_unsupported_type_and_anonymous(self):
        self.assertEqual(self.client.get("/api/documents/").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.register('carol')}")
        f = SimpleUploadedFile("x.exe", b"nope")
        self.assertEqual(self.client.post("/api/documents/", {"file": f}, format="multipart").status_code, 400)


@patch("documents.rag.embed", fake_embed)
@patch("documents.rag.stream_generate", lambda system, messages: iter(["Paris ", "is it [1]."]))
class StreamTests(APITestCase):
    def test_stream_emits_sources_tokens_done(self):
        token = self.client.post("/api/auth/register/", {"username": "dan", "password": "s3cret-pass!"}).json()["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        f = SimpleUploadedFile("a.txt", b"Paris is the capital of France.")
        self.client.post("/api/documents/", {"file": f}, format="multipart")
        r = self.client.post("/api/chat/stream/", {"question": "capital of France?"}, format="json")
        body = b"".join(r.streaming_content).decode()
        self.assertLess(body.index("event: sources"), body.index("event: token"))
        self.assertIn("event: done", body)


@override_settings(OPENAI_API_KEY="", ANTHROPIC_API_KEY="")
class NoKeyModeTests(APITestCase):
    def test_works_without_any_api_key(self):
        token = self.client.post("/api/auth/register/", {"username": "eve", "password": "s3cret-pass!"}).json()["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        text = b"Employees may work remotely up to 3 days per week. The hotel limit in London is 260 dollars."
        r = self.client.post("/api/documents/", {"file": SimpleUploadedFile("h.txt", text)}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        r = self.client.post("/api/chat/stream/", {"question": "How many days remotely?"}, format="json")
        body = b"".join(r.streaming_content).decode()
        self.assertIn("event: sources", body)
        self.assertIn("No AI key is set", body)
