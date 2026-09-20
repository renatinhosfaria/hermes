import sys
import unittest
from pathlib import Path
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_team
ROOT = Path(__file__).resolve().parents[3]

class WorkerChannelPolicyTests(unittest.TestCase):
    def test_administrative_telegram_excludes_commercial_mcp(self):
        for name in ("porteiro", "cadastro", "famaagent"):
            with self.subTest(profile=name):
                config = yaml.safe_load((ROOT / "profiles" / name / "config.yaml").read_text())
                resolved = verify_team.resolve_platform(config, name, "telegram")
                self.assertFalse({"brain", "famachat"} & resolved)
                self.assertTrue({"terminal", "file", "skills", "memory"} <= resolved)

    def test_cli_keeps_commercial_tools_and_authorized_learning(self):
        for name in ("porteiro", "cadastro", "famaagent"):
            with self.subTest(profile=name):
                config = yaml.safe_load((ROOT / "profiles" / name / "config.yaml").read_text())
                resolved = verify_team.resolve_platform(config, name, "cli")
                self.assertTrue({"brain", "famachat", "skills", "memory"} <= resolved)
                for channel in ("cli", "telegram"):
                    self.assertTrue(
                        verify_team.same_toolset_selection(
                            config["platform_toolsets"][channel],
                            verify_team.EXPECTED_PLATFORM_TOOLSETS[name][channel],
                        )
                    )

    def test_toolset_order_is_not_semantic(self):
        expected = ["clarify", "no_mcp", "terminal", "file", "skills", "memory"]
        self.assertTrue(
            verify_team.same_toolset_selection(
                ["memory", "file", "clarify", "terminal", "no_mcp", "skills"],
                expected,
            )
        )
        self.assertFalse(verify_team.same_toolset_selection(expected + ["skills"], expected))

if __name__ == "__main__":
    unittest.main()
