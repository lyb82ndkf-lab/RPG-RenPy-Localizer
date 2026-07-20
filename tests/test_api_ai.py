from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from toolkit.api.server import ApiError, ToolkitApi


class AiApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.api = ToolkitApi(Path(self.temp_dir.name))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_provider_aliases_are_normalized(self) -> None:
        self.assertEqual(self.api._normalize_ai_provider("openai-compatible"), "openai")
        self.assertEqual(self.api._normalize_ai_provider("Claude"), "anthropic")
        self.assertEqual(self.api._normalize_ai_provider("Ollama 本地模型"), "ollama")

    def test_ollama_models_use_native_tags_endpoint_without_key(self) -> None:
        requested = {}

        def fake_get(url: str, _headers: dict, timeout: int = 30) -> dict:
            requested.update({"url": url, "timeout": timeout})
            return {"models": [{"name": "qwen2.5:7b"}, {"model": "gemma3:4b"}]}

        self.api._http_get_json = fake_get
        result = self.api.ai_models({"provider": "ollama", "baseUrl": "http://127.0.0.1:11434", "apiKey": ""})

        self.assertEqual(requested["url"], "http://127.0.0.1:11434/api/tags")
        self.assertEqual(result["models"], ["gemma3:4b", "qwen2.5:7b"])

    def test_ollama_translation_does_not_require_api_key(self) -> None:
        requested = {}

        def fake_post(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
            requested.update({"url": url, "payload": payload, "headers": headers, "timeout": timeout})
            return {"choices": [{"message": {"content": json.dumps(["你好"], ensure_ascii=False)}}]}

        self.api._http_json = fake_post
        result = self.api._translate_openai_compatible(
            ["Hello"], {"provider": "ollama", "baseUrl": "http://127.0.0.1:11434", "model": "qwen2.5:7b", "apiKey": ""}
        )

        self.assertEqual(result, ["你好"])
        self.assertEqual(requested["url"], "http://127.0.0.1:11434/v1/chat/completions")
        self.assertNotIn("Authorization", requested["headers"])

    def test_missing_library_game_returns_readable_error(self) -> None:
        self.api.workspace.load_library = lambda: []
        with self.assertRaises(ApiError) as raised:
            self.api.library_launch({"path": "C:/missing-game"})
        self.assertEqual(raised.exception.status, 404)
        self.assertEqual(str(raised.exception), "游戏库中找不到该游戏。")


if __name__ == "__main__":
    unittest.main()
