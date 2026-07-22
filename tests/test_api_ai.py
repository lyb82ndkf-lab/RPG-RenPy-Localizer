from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from toolkit.api.server import ApiError, ToolkitApi


class AiApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.api = ToolkitApi(root, config_dir=root / "config")

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

    def test_entries_translation_uses_entry_id_protocol_and_timeout(self) -> None:
        requested = {}

        def fake_post(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
            requested.update({"url": url, "payload": payload, "headers": headers, "timeout": timeout})
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"translations": {"e1": "\u4f60\u597d", "e2": "\u518d\u89c1"}}, ensure_ascii=False)
                        }
                    }
                ]
            }

        self.api._http_json = fake_post
        result = self.api.ai_translate({
            "provider": "openai",
            "baseUrl": "https://api.example.com/v1",
            "apiKey": "key",
            "model": "model",
            "requestTimeoutSec": 333,
            "entries": [
                {"entry_id": "e1", "source": "Hello"},
                {"entry_id": "e2", "source": "Bye"},
            ],
        })

        self.assertEqual(requested["timeout"], 333)
        self.assertEqual(requested["payload"]["stream"], False)
        self.assertEqual(requested["payload"]["response_format"], {"type": "json_object"})
        self.assertEqual(requested["payload"]["max_tokens"], 8192)
        self.assertEqual([item["entry_id"] for item in result["translations"]], ["e1", "e2"])
        self.assertEqual([item["target"] for item in result["translations"]], ["\u4f60\u597d", "\u518d\u89c1"])
        user_payload = json.loads(requested["payload"]["messages"][1]["content"])
        self.assertEqual([item["entry_id"] for item in user_payload["entries"]], ["e1", "e2"])

    def test_openai_gateway_without_json_options_is_retried(self) -> None:
        calls = []

        def fake_post(_url: str, payload: dict, _headers: dict, timeout: int = 120) -> dict:
            calls.append(payload.copy())
            if len(calls) == 1:
                raise ApiError("HTTP 400: response_format is not supported", 400)
            return {"choices": [{"message": {"content": '{"translations":{"e1":"你好"}}'}}]}

        self.api._http_json = fake_post
        result = self.api.ai_translate({
            "provider": "openai",
            "baseUrl": "https://api.example.com/v1",
            "apiKey": "key",
            "model": "model",
            "entries": [{"entry_id": "e1", "source": "Hello"}],
        })

        self.assertEqual(len(calls), 2)
        self.assertNotIn("response_format", calls[1])
        self.assertNotIn("max_tokens", calls[1])
        self.assertEqual(result["translations"][0]["target"], "你好")

    def test_missing_library_game_returns_readable_error(self) -> None:
        self.api.workspace.load_library = lambda: []
        with self.assertRaises(ApiError) as raised:
            self.api.library_launch({"path": "C:/missing-game"})
        self.assertEqual(raised.exception.status, 404)
        self.assertEqual(str(raised.exception), "游戏库中找不到该游戏。")

    def test_library_folder_import_recursively_detects_supported_games_once(self) -> None:
        root = Path(self.temp_dir.name) / "bulk"
        rpg = root / "Project1"
        renpy = root / "Novel"
        junk = root / "Other"
        sample = root / "TilesetSample"
        (rpg / "data").mkdir(parents=True)
        (rpg / "js" / "plugins").mkdir(parents=True)
        (rpg / "js" / "plugins.js").write_text("var $plugins = [];", encoding="utf-8")
        (rpg / "data" / "System.json").write_text("{}", encoding="utf-8")
        (rpg / "Project1.exe").write_bytes(b"fake")
        (rpg / "www" / "data").mkdir(parents=True)
        (rpg / "www" / "data" / "System.json").write_text("{}", encoding="utf-8")
        (renpy / "game").mkdir(parents=True)
        (renpy / "game" / "script.rpy").write_text("label start:\n    return\n", encoding="utf-8")
        (renpy / "Novel.exe").write_bytes(b"fake")
        (renpy / "game" / "audio" / "game").mkdir(parents=True)
        (renpy / "game" / "audio" / "game" / "script.rpy").write_text("label nested:\n    return\n", encoding="utf-8")
        (renpy / "game" / "audio" / "audio.exe").write_bytes(b"fake")
        (renpy / ".rpgrtl_backup" / "game").mkdir(parents=True)
        (renpy / ".rpgrtl_backup" / "game" / "script.rpy").write_text("label backup:\n    return\n", encoding="utf-8")
        junk.mkdir(parents=True)
        (junk / "Other.exe").write_bytes(b"fake")
        (sample / "data").mkdir(parents=True)
        (sample / "data" / "System.json").write_text("{}", encoding="utf-8")

        result = self.api.library_add_folder({"path": str(root)})
        entries = result["entries"]
        paths = {item["path"] for item in entries}

        self.assertEqual(result["added"], 2)
        self.assertEqual(result["found"], 2)
        self.assertIn(str(rpg.resolve()), paths)
        self.assertIn(str(renpy.resolve()), paths)
        self.assertEqual(len(paths), len(entries))
        self.assertNotIn(str((rpg / "www").resolve()), paths)
        self.assertNotIn(str((renpy / "game" / "audio").resolve()), paths)
        self.assertNotIn(str((renpy / ".rpgrtl_backup").resolve()), paths)
        self.assertNotIn(str(sample.resolve()), paths)

    def test_workspace_reads_bom_prefixed_library_json(self) -> None:
        config = Path(self.temp_dir.name) / "bom-config"
        config.mkdir()
        (config / "library.json").write_text('{"games":[]}', encoding="utf-8-sig")
        api = ToolkitApi(Path(self.temp_dir.name) / "project", config_dir=config)

        result = api.library_get()

        self.assertEqual(result["entries"], [])


if __name__ == "__main__":
    unittest.main()
