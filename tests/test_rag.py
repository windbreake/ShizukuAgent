from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agent.embeddings import make_embedder
from app.config import settings
from app.storage.adapter import StorageAdapter, _cosine, _embed_text


class FakeLLM:
    def __init__(self, vector: list[float] | None) -> None:
        self.vector = vector
        self.calls = 0

    def embed(self, text: str, model_config=None):
        self.calls += 1
        if self.vector is None:
            raise RuntimeError("embedding unavailable")
        return list(self.vector)


class EmbeddingTests(unittest.TestCase):
    def test_make_embedder_prefers_llm(self) -> None:
        llm = FakeLLM([1.0, 0.0, 0.0])
        embed = make_embedder(llm)
        self.assertEqual([1.0, 0.0, 0.0], embed("hello"))
        self.assertEqual(1, llm.calls)

    def test_make_embedder_falls_back_on_error(self) -> None:
        llm = FakeLLM(None)
        embed = make_embedder(llm)
        result = embed("hello world")
        self.assertEqual(len(_embed_text("hello world")), len(result))
        self.assertEqual(1, llm.calls)

    def test_cosine_dimension_mismatch_returns_zero(self) -> None:
        self.assertEqual(0.0, _cosine([1.0, 0.0], [1.0, 0.0, 0.0]))

    def test_cosine_normalizes_unnormalized_vectors(self) -> None:
        self.assertAlmostEqual(1.0, _cosine([2.0, 0.0], [1.0, 0.0]))
        self.assertAlmostEqual(0.0, _cosine([1.0, 0.0], [0.0, 1.0]))


class StorageEmbedderTests(unittest.TestCase):
    def test_empty_persona_skips_embedding_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = self._make_storage(tmp)
            try:
                llm = FakeLLM([1.0, 0.0])
                storage.set_embedder(make_embedder(llm))
                storage.add_memory('other', 'unrelated memory')
                llm.calls = 0
                self.assertEqual([], storage.search_memories('hello', persona='empty'))
                self.assertEqual(0, llm.calls)
            finally:
                storage._conn.close()

    def _make_storage(self, tmp: str) -> StorageAdapter:
        db_path = Path(tmp) / "test.db"
        with patch.object(settings, "_data", {"storage": {"sqlite": {"path": str(db_path)}}}):
            storage = StorageAdapter()
        return storage

    def test_storage_uses_injected_embedder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = self._make_storage(tmp)
            try:
                storage.set_embedder(lambda text: [1.0, 0.0])
                storage.add_memory("shizuku", "hello world", kind="long_term")
                items = storage.search_memories("hello", persona="shizuku", top_k=1)
                self.assertEqual("hello world", items[0]["content"])
                self.assertGreaterEqual(items[0]["score"], 0.99)
            finally:
                storage._conn.close()

    def test_search_min_score_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = self._make_storage(tmp)
            try:
                storage.set_embedder(lambda text: [1.0, 0.0])
                storage.add_memory("shizuku", "hello world", kind="long_term")
                filtered = storage.search_memories("hello", persona="shizuku", top_k=5, min_score=0.99)
                self.assertEqual(1, len(filtered))
                empty = storage.search_memories("hello", persona="shizuku", top_k=5, min_score=1.01)
                self.assertEqual(0, len(empty))
            finally:
                storage._conn.close()

    def test_reindex_memories_updates_embeddings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = self._make_storage(tmp)
            try:
                storage.set_embedder(lambda text: [1.0, 0.0])
                storage.add_memory("shizuku", "hello world", kind="long_term")
                storage.set_embedder(lambda text: [0.0, 1.0])
                updated = storage.reindex_memories(persona="shizuku")
                self.assertEqual(1, updated)
                items = storage.search_memories("x", persona="shizuku", top_k=1)
                self.assertGreaterEqual(items[0]["score"], 0.99)
            finally:
                storage._conn.close()


if __name__ == "__main__":
    unittest.main()
