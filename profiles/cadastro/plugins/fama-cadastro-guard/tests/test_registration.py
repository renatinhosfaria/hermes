"""Offline checks of production MCP access outside a dispatched worker."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("cadastro_profile_guard", Path(__file__).resolve().parents[1] / "__init__.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class Context:
    def __init__(self):
        self.hooks = {}

    def register_hook(self, name, fn):
        self.hooks[name] = fn


class RegistrationTests(unittest.TestCase):
    def context(self, **extra):
        ctx = Context()
        with patch.dict(os.environ, {"HERMES_PROFILE": "cadastro", **extra}, clear=True):
            guard.register(ctx)
        return ctx

    def test_nonworker_blocks_direct_and_wrapped_business_calls(self):
        for env in ({}, {"HERMES_KANBAN_TASK": "task"}, {"HERMES_KANBAN_RUN_ID": "1"}):
            ctx = self.context(**env)
            self.assertIn("pre_tool_call", ctx.hooks)
            for name in (guard.BRAIN, guard.SEARCH, guard.POST, guard.READ):
                for tool, args in ((name, {}), ("tool_call", {"name": name, "arguments": {}})):
                    with self.subTest(env=env, tool=tool, name=name):
                        result = ctx.hooks["pre_tool_call"](tool_name=tool, args=args)
                        self.assertEqual(result["action"], "block")

    def test_maintenance_and_learning_remain_available(self):
        ctx = self.context()
        self.assertIn("pre_tool_call", ctx.hooks)
        for name in ("terminal", "read_file", "write_file", "patch", "memory", "skill_manage", "kanban_show"):
            self.assertIsNone(ctx.hooks["pre_tool_call"](tool_name=name, args={}))

    def test_worker_retains_stateful_validation(self):
        ctx = self.context(HERMES_KANBAN_TASK="task", HERMES_KANBAN_RUN_ID="1")
        self.assertEqual(set(ctx.hooks), {"pre_tool_call", "post_tool_call", "transform_tool_result"})
        result = ctx.hooks["pre_tool_call"](tool_name=guard.POST, args={}, session_id="session", tool_call_id="1")
        self.assertEqual(result["action"], "block")

    def test_other_profiles_are_untouched(self):
        self.assertFalse(self.context(HERMES_PROFILE="other").hooks)

    def test_native_profile_selection_without_profile_variable_blocks_business(self):
        ctx = Context()
        with patch.dict(os.environ, {"HERMES_HOME": str(Path(__file__).resolve().parents[3])}, clear=True):
            guard.register(ctx)
        self.assertIn("pre_tool_call", ctx.hooks)
        self.assertEqual(ctx.hooks["pre_tool_call"](tool_name=guard.POST, args={})["action"], "block")


if __name__ == "__main__":
    unittest.main()
