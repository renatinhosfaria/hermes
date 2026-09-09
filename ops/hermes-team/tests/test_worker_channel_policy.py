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
                    self.assertEqual(config["platform_toolsets"][channel], verify_team.EXPECTED_PLATFORM_TOOLSETS[name][channel])

if __name__ == "__main__":
    unittest.main()
