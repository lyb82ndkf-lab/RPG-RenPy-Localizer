from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from toolkit.api.server import ApiError, ToolkitApi
from toolkit.models import TranslationEntry
from toolkit.storage import export_translation_pack, import_translation_pack
from toolkit.workspace import LibraryEntry


class AiApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.api = ToolkitApi(root, config_dir=root / "config")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_preflight_rejects_missing_template_tokens_for_galgame(self) -> None:
        game_root = Path(self.temp_dir.name) / "galgame"
        game_root.mkdir()
        (game_root / "krkr.exe").write_bytes(b"MZ")
        self.api.load_project({"path": str(game_root)})
        self.api.translation_entries = [TranslationEntry(
            "line-1", "Hello, {player}! \\N[4]", "", "script.json", "galtransl-json;row=0", "galgame_dialogue"
        )]
        with self.assertRaises(ApiError):
            self.api.translations_save_targets({"updates": [{"entry_id": "line-1", "target": "??????"}]})
        result = self.api.translations_save_targets({"updates": [{"entry_id": "line-1", "target": "???{player}? \\N[4]"}]})
        self.assertEqual(result["changed"], 1)
        report = self.api.translations_preflight({})
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["verifiedWriteback"], 1)

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

    def test_entries_translation_preserves_file_context_in_prompt(self) -> None:
        requested = {}

        def fake_post(_url: str, payload: dict, _headers: dict, timeout: int = 120) -> dict:
            requested["payload"] = payload
            return {"choices": [{"message": {"content": '{"translations":{"e1":"你好"}}'}}]}

        self.api._http_json = fake_post
        self.api.ai_translate({
            "provider": "openai", "baseUrl": "https://api.example.com/v1", "apiKey": "key", "model": "model",
            "entries": [{"entry_id": "e1", "source": "Hello", "file": "Map001.json", "context": "event code 401"}],
        })

        user_payload = json.loads(requested["payload"]["messages"][1]["content"])
        self.assertEqual(user_payload["source_files"], ["Map001.json"])
        self.assertEqual(user_payload["entries"][0]["context"], "event code 401")

    def test_symbol_and_numeric_entries_are_confirmed_without_ai_request(self) -> None:
        self.api.project = SimpleNamespace(root=Path(self.temp_dir.name))
        called = []
        self.api._translate_entries_openai_compatible = lambda entries, _body: called.append(entries) or []  # type: ignore[method-assign]

        result = self.api.ai_translate({
            "provider": "openai", "entries": [
                {"entry_id": "dots", "source": "...?!"},
                {"entry_id": "number", "source": "12345"},
                {"entry_id": "word", "source": "Hello"},
            ],
        })

        self.assertEqual(called, [[{"entry_id": "word", "source": "Hello", "file": "", "context": "", "category": ""}]])
        self.assertEqual([item["target"] for item in result["translations"]], ["...?!", "12345", ""])

    def test_export_uses_persisted_entries_not_stale_renderer_snapshot(self) -> None:
        root = Path(self.temp_dir.name)
        self.api.project = SimpleNamespace(root=root, engine="RPG Maker MV/MZ")
        self.api.translation_entries = [TranslationEntry("row", "Hello", "你好", "Map001.json", category="dialogue")]
        path = root / "export.json"

        self.api.translations_export({"path": str(path), "entries": [{"entry_id": "row", "source": "Hello", "target": ""}]})

        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"Hello": "你好"})

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

    def test_library_load_prunes_missing_game_paths(self) -> None:
        missing = Path(self.temp_dir.name) / "missing-game"
        valid = Path(self.temp_dir.name) / "valid-game"
        valid.mkdir()
        launcher = valid / "Game.exe"
        launcher.write_bytes(b"fake")
        self.api.workspace.save_library([
            LibraryEntry("Missing", str(missing), "Ren'Py", "", launcher_path=str(missing / "Game.exe")),
            LibraryEntry("Valid", str(valid), "Ren'Py", "", launcher_path=str(launcher)),
        ])

        result = self.api.library_get()

        self.assertEqual(result["removed"], 1)
        self.assertEqual([entry["name"] for entry in result["entries"]], ["Valid"])
        self.assertEqual([entry.name for entry in self.api.workspace.load_library()], ["Valid"])

    def test_user_translation_pack_is_a_plain_source_to_target_map(self) -> None:
        path = Path(self.temp_dir.name) / "translation.json"
        export_translation_pack(path, "RPG Maker MV/MZ", [
            TranslationEntry("Actors.json::1/name", "校庭", "校园", "Actors.json", category="database"),
            TranslationEntry("Map001.json::4", "場所移動", "场景切换", "Map001.json", category="dialogue"),
        ])

        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"校庭": "校园", "場所移動": "场景切换"})
        imported = import_translation_pack(path)
        self.assertEqual(imported["校庭"].target, "校园")
        self.assertEqual(imported["校庭"].entry_id, "")

    def test_ai_translation_deduplicates_entries_and_uses_project_cache(self) -> None:
        self.api.project = SimpleNamespace(root=Path(self.temp_dir.name))
        calls: list[list[str]] = []

        def fake_translate(entries: list[dict], _body: dict) -> list[dict]:
            calls.append([entry["source"] for entry in entries])
            return [{"entry_id": entry["entry_id"], "target": "译-" + entry["source"]} for entry in entries]

        self.api._translate_entries_openai_compatible = fake_translate  # type: ignore[method-assign]
        payload = {"provider": "OpenAI", "targetLang": "简体中文", "entries": [
            {"entry_id": "a", "source": "Same", "file": "A.json"},
            {"entry_id": "b", "source": "Same", "file": "B.json"},
            {"entry_id": "c", "source": "Other"},
        ]}

        first = self.api.ai_translate(payload)
        second = self.api.ai_translate(payload)

        self.assertEqual(calls, [["Same", "Other"]])
        self.assertEqual([item["target"] for item in first["translations"]], ["译-Same", "译-Same", "译-Other"])
        self.assertEqual(second["requested"], 0)

    def test_account_bridge_uses_codex_cli_directly_without_pi_bridge(self) -> None:
        captured: list[list[str]] = []

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            captured.append(command)
            return SimpleNamespace(returncode=0, stdout='{"translations":{"a":"你好"}}', stderr="")

        with patch.object(self.api, "_native_agent_bin", return_value="codex"), patch("toolkit.api.server.subprocess.run", side_effect=fake_run):
            result = self.api.ai_translate({
                "provider": "accountbridge",
                "accountProvider": "openai-codex",
                "model": "gpt-5.4-mini",
                "targetLang": "简体中文",
                "entries": [{"entry_id": "a", "source": "Hello"}],
            })

        self.assertEqual(result["translations"], [{"entry_id": "a", "target": "你好"}])
        self.assertEqual(captured[0][0], "codex")
        self.assertIn("exec", captured[0])
        self.assertIn("--model", captured[0])
        self.assertEqual(captured[0][captured[0].index("--model") + 1], "gpt-5.4-mini")
        self.assertNotIn("--provider", captured[0])

    def test_account_bridge_rejects_unsupported_subscription_account(self) -> None:
        with self.assertRaises(ApiError) as raised:
            self.api.ai_models({"provider": "accountbridge", "accountProvider": "unknown-agent"})
        self.assertIn("Agent CLI", str(raised.exception))

    @unittest.skip("Gemini account bridge now uses browser OAuth tokens directly instead of launching Gemini CLI.")
    def test_gemini_cli_bridge_uses_google_account_cli_not_pi(self) -> None:
        captured: list[list[str]] = []

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            captured.append(command)
            return SimpleNamespace(returncode=0, stdout='{"response":"{\\"translations\\":{\\"a\\":\\"你好\\"}}"}', stderr="")

        with patch("toolkit.api.server.subprocess.run", side_effect=fake_run):
            result = self.api.ai_translate({
                "provider": "accountbridge",
                "accountProvider": "gemini-cli",
                "model": "gemini-2.5-flash",
                "entries": [{"entry_id": "a", "source": "Hello"}],
            })

        self.assertEqual(result["translations"], [{"entry_id": "a", "target": "你好"}])
        self.assertEqual(captured[0][0], "gemini")
        self.assertIn("--prompt", captured[0])
        self.assertIn("--output-format", captured[0])

    def test_gemini_cli_bridge_uses_browser_oauth_token_not_cli_process(self) -> None:
        credential = {
            "provider": "google-gemini-cli",
            "refresh": "refresh-token",
            "access": "access-token",
            "expires": 4102444800000,
            "projectId": "cloud-code-project",
        }
        (self.api.workspace.config_dir / "google-gemini-cli-oauth.json").write_text(json.dumps(credential), encoding="utf-8")

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                payload = {
                    "response": {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {"text": '{"translations":{"a":"Hello-ZH"}}'}
                                    ]
                                }
                            }
                        ]
                    }
                }
                return ("data: " + json.dumps(payload) + "\n\n").encode("utf-8")

        with patch("toolkit.api.server.urllib.request.urlopen", return_value=FakeResponse()), patch("toolkit.api.server.subprocess.run") as run:
            result = self.api.ai_translate({
                "provider": "accountbridge",
                "accountProvider": "gemini-cli",
                "model": "gemini-2.5-flash",
                "entries": [{"entry_id": "a", "source": "Hello"}],
            })

        self.assertEqual(result["translations"], [{"entry_id": "a", "target": "Hello-ZH"}])
        run.assert_not_called()

    def test_gemini_cli_models_include_current_google_flash_models(self) -> None:
        result = self.api.ai_models({"provider": "accountbridge", "accountProvider": "gemini-cli"})

        self.assertGreaterEqual(result["models"].index("gemini-3.6-flash"), 0)
        self.assertIn("gemini-3.5-flash", result["models"])
        self.assertIn("gemini-3.5-flash-lite", result["models"])
        self.assertLess(result["models"].index("gemini-3.6-flash"), result["models"].index("gemini-2.5-flash"))

    def test_gemini_cli_bridge_keeps_existing_access_when_refresh_is_rejected(self) -> None:
        credential = {
            "provider": "google-gemini-cli",
            "refresh": "stale-refresh-token",
            "access": "still-usable-access-token",
            "expires": 0,
            "projectId": "cloud-code-project",
        }
        credential_path = self.api.workspace.config_dir / "google-gemini-cli-oauth.json"
        credential_path.write_text(json.dumps(credential), encoding="utf-8")
        auth_headers: list[str] = []

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                payload = {"response": {"candidates": [{"content": {"parts": [{"text": '{"translations":{"a":"Hello-ZH"}}'}]}}]}}
                return ("data: " + json.dumps(payload) + "\n\n").encode("utf-8")

        def fake_urlopen(request: object, **_kwargs: object) -> FakeResponse:
            url = str(getattr(request, "full_url", ""))
            if "oauth2.googleapis.com/token" in url:
                raise urllib.error.HTTPError(url, 401, "Unauthorized", hdrs=None, fp=None)
            if "streamGenerateContent" in url:
                headers = getattr(request, "headers", {})
                auth_headers.append(str(headers.get("Authorization") or headers.get("authorization") or ""))
                return FakeResponse()
            raise AssertionError(f"unexpected url: {url}")

        with patch("toolkit.api.server.urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.api.ai_translate({
                "provider": "accountbridge",
                "accountProvider": "gemini-cli",
                "model": "gemini-3.6-flash",
                "entries": [{"entry_id": "a", "source": "Hello"}],
            })

        self.assertEqual(result["translations"], [{"entry_id": "a", "target": "Hello-ZH"}])
        self.assertEqual(auth_headers, ["Bearer still-usable-access-token"])
        saved = json.loads(credential_path.read_text(encoding="utf-8"))
        self.assertIn("refreshError", saved)

    def test_account_bridge_auto_uses_logged_in_antigravity_cli(self) -> None:
        captured: dict[str, object] = {}

        def fake_bin(provider: str) -> str:
            self.assertEqual(provider, "antigravity-cli")
            return "agy"

        def fake_available(provider: str) -> bool:
            return provider == "antigravity-cli"

        def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
            captured["command"] = command
            captured["input"] = kwargs.get("input")
            return SimpleNamespace(returncode=0, stdout='{"translations":{"a":"你好"}}', stderr="")

        with (
            patch.object(self.api, "_native_agent_bin", side_effect=fake_bin),
            patch.object(self.api, "_native_agent_available", side_effect=fake_available),
            patch.object(self.api, "_write_antigravity_model_selection") as write_model,
            patch("toolkit.api.server.subprocess.run", side_effect=fake_run),
        ):
            result = self.api.ai_translate({
                "provider": "accountbridge",
                "accountProvider": "local-agent-auto",
                "model": "antigravity-cli:Gemini 3.5 Flash (High)",
                "entries": [{"entry_id": "a", "source": "Hello"}],
            })

        self.assertEqual(result["translations"], [{"entry_id": "a", "target": "你好"}])
        self.assertEqual(captured["command"][0], "agy")
        self.assertEqual(captured["command"][1], "--log-file")
        self.assertIn("--model", captured["command"])
        self.assertEqual(captured["command"][captured["command"].index("--model") + 1], "gemini-3.5-flash-high")
        self.assertIn("-p", captured["command"])
        self.assertNotEqual(captured["command"][captured["command"].index("-p") + 1], "-")
        self.assertIn('"entry_id": "a"', captured["command"][captured["command"].index("-p") + 1])
        self.assertIsNone(captured["input"])
        write_model.assert_called_once_with("gemini-3.5-flash-high")

    def test_account_bridge_single_plain_agent_response_is_used_as_translation(self) -> None:
        def fake_run(_command: list[str], **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(returncode=0, stdout='你好，欢迎来到游戏。', stderr="")

        with (
            patch.object(self.api, "_native_agent_bin", return_value="agy"),
            patch.object(self.api, "_native_agent_available", return_value=True),
            patch("toolkit.api.server.subprocess.run", side_effect=fake_run),
        ):
            result = self.api.ai_translate({
                "provider": "accountbridge",
                "accountProvider": "local-agent-auto",
                "model": "antigravity-cli:default",
                "texts": ["Hello, welcome to the game."],
            })

        self.assertEqual(result["translations"], ["你好，欢迎来到游戏。"])

    def test_account_bridge_jsonl_agent_response_is_unwrapped_before_parsing(self) -> None:
        payload = {"translations": {"0": "你好"}}

        def fake_run(_command: list[str], **_kwargs: object) -> SimpleNamespace:
            stdout = "\n".join([
                json.dumps({"type": "started", "text": ""}),
                json.dumps({"type": "message", "message": json.dumps(payload, ensure_ascii=False)}, ensure_ascii=False),
            ])
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

        with patch.object(self.api, "_native_agent_bin", return_value="codex"), patch("toolkit.api.server.subprocess.run", side_effect=fake_run):
            result = self.api.ai_translate({
                "provider": "accountbridge",
                "accountProvider": "openai-codex",
                "model": "default",
                "texts": ["Hello"],
            })

        self.assertEqual(result["translations"], ["你好"])

    def test_account_bridge_models_expose_native_agent_auto_and_antigravity_models(self) -> None:
        auto = self.api.ai_models({"provider": "accountbridge", "accountProvider": "local-agent-auto"})
        agy = self.api.ai_models({"provider": "accountbridge", "accountProvider": "antigravity-cli"})

        self.assertIn("antigravity-cli:gemini-3.5-flash-high", auto["models"])
        self.assertIn("openai-codex:gpt-5.4", auto["models"])
        self.assertIn("gemini-3.5-flash-high", agy["models"])

    def test_gemini_cli_bridge_discovers_project_when_oauth_file_has_no_project(self) -> None:
        credential = {
            "provider": "google-gemini-cli",
            "refresh": "refresh-token",
            "access": "access-token",
            "expires": 4102444800000,
        }
        credential_path = self.api.workspace.config_dir / "google-gemini-cli-oauth.json"
        credential_path.write_text(json.dumps(credential), encoding="utf-8")
        seen_stream_body: dict[str, object] = {}

        class FakeResponse:
            def __init__(self, payload: object, sse: bool = False) -> None:
                self.payload = payload
                self.sse = sse

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                if self.sse:
                    return ("data: " + json.dumps(self.payload) + "\n\n").encode("utf-8")
                return json.dumps(self.payload).encode("utf-8")

        def fake_urlopen(request: object, **_kwargs: object) -> FakeResponse:
            url = str(getattr(request, "full_url", ""))
            raw_data = getattr(request, "data", None)
            if "loadCodeAssist" in url:
                return FakeResponse({"allowedTiers": [{"id": "standard-tier", "isDefault": True}]})
            if "onboardUser" in url:
                return FakeResponse({"name": "operations/provision-test", "done": False})
            if "operations/provision-test" in url:
                return FakeResponse({"done": True, "response": {"cloudaicompanionProject": {"id": "provisioned-project"}}})
            if "streamGenerateContent" in url:
                if isinstance(raw_data, bytes):
                    seen_stream_body.update(json.loads(raw_data.decode("utf-8")))
                payload = {"response": {"candidates": [{"content": {"parts": [{"text": '{"translations":{"a":"Hello-ZH"}}'}]}}]}}
                return FakeResponse(payload, sse=True)
            raise AssertionError(f"unexpected url: {url}")

        with patch("toolkit.api.server.urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.api.ai_translate({
                "provider": "accountbridge",
                "accountProvider": "gemini-cli",
                "model": "gemini-2.5-flash",
                "entries": [{"entry_id": "a", "source": "Hello"}],
            })

        self.assertEqual(result["translations"], [{"entry_id": "a", "target": "Hello-ZH"}])
        self.assertEqual(seen_stream_body["project"], "provisioned-project")
        saved = json.loads(credential_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["projectId"], "provisioned-project")

    def test_gemini_cli_bridge_falls_back_to_generative_language_when_project_missing(self) -> None:
        credential = {
            "provider": "google-gemini-cli",
            "refresh": "refresh-token",
            "access": "access-token",
            "expires": 4102444800000,
        }
        credential_path = self.api.workspace.config_dir / "google-gemini-cli-oauth.json"
        credential_path.write_text(json.dumps(credential), encoding="utf-8")
        called_urls: list[str] = []

        class FakeResponse:
            def __init__(self, payload: object) -> None:
                self.payload = payload

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(self.payload).encode("utf-8")

        def fake_urlopen(request: object, **_kwargs: object) -> FakeResponse:
            url = str(getattr(request, "full_url", ""))
            called_urls.append(url)
            if "loadCodeAssist" in url:
                return FakeResponse({"allowedTiers": [{"id": "free-tier", "isDefault": True}]})
            if "onboardUser" in url:
                return FakeResponse({"done": True, "response": {}})
            if "generativelanguage.googleapis.com" in url:
                return FakeResponse({"candidates": [{"content": {"parts": [{"text": '{"translations":{"a":"Hello-ZH"}}'}]}}]})
            raise AssertionError(f"unexpected url: {url}")

        with patch("toolkit.api.server.urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.api.ai_translate({
                "provider": "accountbridge",
                "accountProvider": "gemini-cli",
                "model": "gemini-2.5-flash",
                "entries": [{"entry_id": "a", "source": "Hello"}],
            })

        self.assertEqual(result["translations"], [{"entry_id": "a", "target": "Hello-ZH"}])
        self.assertTrue(any("generativelanguage.googleapis.com" in url for url in called_urls))
        saved = json.loads(credential_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["projectId"], "")
        self.assertIn("projectDiscoveryError", saved)

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
