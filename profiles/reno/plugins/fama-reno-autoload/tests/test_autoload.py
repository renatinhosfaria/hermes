"""Run with the Hermes interpreter; fixtures never touch customer data."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reno_autoload", PLUGIN / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class AutoloadTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "reno"
        self.root = self.home / "skills/business-operations/fama-reno-runtime"
        self.files = ["SKILL.md", "references/conversa.md", "references/fontes.md",
                      "references/crm.md", "references/agendamento.md"]
        for name in self.files:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"Conteúdo original de {name}\n", encoding="utf-8")

    def register(self):
        hooks = {}
        self.middleware = {}
        middleware = self.middleware

        class Context:
            def register_hook(self, name, callback):
                hooks[name] = callback

            def register_middleware(self, name, callback):
                middleware[name] = callback

        with patch("hermes_constants.get_hermes_home", return_value=self.home):
            plugin.register(Context())
        self.assertEqual(list(hooks), ["pre_llm_call"])
        return hooks["pre_llm_call"]

    def test_multimodal_request_preserves_images_history_and_tool_results(self):
        from copy import deepcopy
        self.register()
        callback = self.middleware["llm_request"]
        for key, text_type in [("messages", "text"), ("input", "input_text")]:
            picture = ({"type": "image_url", "image_url": {"url": "https://example.invalid/fixture.png"}}
                       if key == "messages" else
                       {"type": "input_image", "image_url": "https://example.invalid/fixture.png"})
            request = {key: [
                {"role": "user", "content": "Histórico anterior"},
                {"role": "user", "content": [
                    {"type": text_type, "text": "Analise esta imagem"},
                    picture,
                ]},
                {"role": "tool", "content": "Resultado sintético", "tool_call_id": "test"},
            ], "model": "synthetic"}
            before = deepcopy(request)
            with patch("hermes_constants.get_hermes_home", return_value=self.home):
                rewritten = callback(request=request)["request"]
                self.assertIsNone(callback(request=rewritten))
            self.assertEqual(request, before)
            self.assertEqual(rewritten[key][0], before[key][0])
            self.assertEqual(rewritten[key][-1], before[key][-1])
            self.assertEqual(rewritten[key][1]["content"][:2], before[key][1]["content"])
            added = rewritten[key][1]["content"][-1]
            self.assertEqual(added["type"], text_type)
            for name in self.files:
                self.assertIn((self.root / name).read_text(), added["text"])

    def test_middleware_leaves_text_and_other_profiles_unchanged(self):
        self.register()
        callback = self.middleware["llm_request"]
        with patch("hermes_constants.get_hermes_home", return_value=self.home):
            self.assertIsNone(callback(request={"messages": [{"role": "user", "content": "Texto"}]}))
        with patch("hermes_constants.get_hermes_home", return_value=self.home.parent / "other"):
            self.assertIsNone(callback(request={"messages": [{"role": "user", "content": []}]}))

    def test_responses_text_conversion_does_not_duplicate_hook_bundle(self):
        hook = self.register()
        callback = self.middleware["llm_request"]
        with patch("hermes_constants.get_hermes_home", return_value=self.home):
            converted = {"input": [{"role": "user", "content": [
                {"type": "input_text", "text": "Texto original\n\n" + hook()["context"]}
            ]}]}
            self.assertIsNone(callback(request=converted))

    def test_every_platform_and_subsequent_turn_includes_all_files(self):
        callback = self.register()
        with patch("hermes_constants.get_hermes_home", return_value=self.home):
            for platform in ["cli", "telegram", "whatsapp", ""]:
                for first in [True, False]:
                    context = callback(platform=platform, is_first_turn=first,
                                       task_id="synthetic", future_kwarg=True)["context"]
                    self.assertIn('status="complete"', context)
                    for name in self.files:
                        self.assertIn((self.root / name).read_text(), context)

    def test_reloads_current_content_every_turn(self):
        callback = self.register()
        with patch("hermes_constants.get_hermes_home", return_value=self.home):
            before = callback()["context"]
            (self.root / self.files[-1]).write_text("Horário revisado\n")
            after = callback()["context"]
        self.assertNotEqual(before, after)
        self.assertIn("Horário revisado", after)

    def test_does_not_leak_into_another_profile(self):
        callback = self.register()
        with patch("hermes_constants.get_hermes_home", return_value=self.home.parent / "other"):
            self.assertIsNone(callback())

    def test_missing_empty_or_blocked_file_never_claims_complete(self):
        target = self.root / self.files[-1]
        callback = self.register()
        with patch("hermes_constants.get_hermes_home", return_value=self.home):
            for content in [None, "", "Arquivo sintético"]:
                if content is None:
                    target.unlink()
                else:
                    target.write_text(content)
                with patch("agent.prompt_builder._scan_context_content",
                           side_effect=lambda text, name: "[BLOCKED: fixture]" if text == "Arquivo sintético" else text):
                    context = callback()["context"]
                self.assertIn('status="error"', context)
                self.assertNotIn('status="complete"', context)
                self.assertNotIn("Conteúdo original", context)


if __name__ == "__main__":
    main()
