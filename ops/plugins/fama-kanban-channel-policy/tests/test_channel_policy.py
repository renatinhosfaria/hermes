from __future__ import annotations

import ast
import importlib.util
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway import kanban_watchers
from hermes_cli import kanban_db as kb


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def load_plugin():
    spec = importlib.util.spec_from_file_location(
        "fama_kanban_channel_policy", PLUGIN_DIR / "__init__.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_subscription(conn, task_id: str, platform: str, mode: str) -> None:
    kb.add_notify_sub(
        conn,
        task_id=task_id,
        platform=platform,
        chat_id=f"fictional-{platform}-chat",
        thread_id=f"fictional-{platform}-thread",
        user_id=f"fictional-{platform}-user",
        user_id_alt=f"fictional-{platform}-alt",
        chat_type="dm",
        notifier_profile="default",
        delivery_mode=mode,
        delivery_metadata={"synthetic": True, "platform": platform},
    )


def modes_by_platform(conn, task_id: str) -> dict[str, str]:
    return {
        row["platform"]: row["delivery_mode"]
        for row in kb.list_notify_subs(conn, task_id)
    }


class ChannelPolicyTests(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "kanban.db"
        self.conn = kb.connect(self.db_path)
        self.task_id = kb.create_task(
            self.conn,
            title="synthetic",
            assignee="dev",
            initial_status="blocked",
        )

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def enforce(self) -> bool:
        return self.plugin.enforce_whatsapp_wake_only(
            task_id=self.task_id,
            db_path=self.db_path,
        )

    def test_whatsapp_notify_wake_becomes_wake_and_preserves_routing(self):
        add_subscription(self.conn, self.task_id, "whatsapp", "notify+wake")
        before = kb.list_notify_subs(self.conn, self.task_id)[0]

        self.assertTrue(self.enforce())

        after = kb.list_notify_subs(self.conn, self.task_id)[0]
        self.assertEqual(after["delivery_mode"], "wake")
        preserved = {
            "task_id",
            "platform",
            "chat_id",
            "thread_id",
            "user_id",
            "user_id_alt",
            "chat_type",
            "notifier_profile",
            "delivery_metadata",
            "created_at",
            "last_event_id",
        }
        self.assertEqual(
            {key: after[key] for key in preserved},
            {key: before[key] for key in preserved},
        )

    def test_telegram_is_unchanged(self):
        add_subscription(self.conn, self.task_id, "telegram", "notify+wake")

        self.assertTrue(self.enforce())

        self.assertEqual(
            modes_by_platform(self.conn, self.task_id),
            {"telegram": "notify+wake"},
        )

    def test_existing_whatsapp_wake_is_idempotent(self):
        add_subscription(self.conn, self.task_id, "whatsapp", "wake")
        before = kb.list_notify_subs(self.conn, self.task_id)

        self.assertTrue(self.enforce())
        self.assertTrue(self.enforce())

        after = kb.list_notify_subs(self.conn, self.task_id)
        self.assertEqual(after, before)
        self.assertEqual(len(after), 1)

    def test_mixed_subscriptions_only_change_whatsapp(self):
        add_subscription(self.conn, self.task_id, "whatsapp", "notify+wake")
        add_subscription(self.conn, self.task_id, "telegram", "notify+wake")

        self.assertTrue(self.enforce())

        self.assertEqual(
            modes_by_platform(self.conn, self.task_id),
            {"whatsapp": "wake", "telegram": "notify+wake"},
        )

    def test_task_without_subscription_fails_safely(self):
        with self.assertLogs(level="ERROR") as logs:
            self.assertFalse(self.enforce())

        self.assertEqual(kb.list_notify_subs(self.conn, self.task_id), [])
        self.assertTrue(
            any("policy enforcement failed" in line for line in logs.output)
        )
        self.assertFalse(any(self.task_id in line for line in logs.output))

    def test_claim_hook_enforces_before_spawn(self):
        events: list[str] = []
        registered: dict[str, object] = {}

        class Context:
            def register_hook(inner_self, name, callback):
                registered["name"] = name
                registered["callback"] = callback

        self.plugin.register(Context())
        self.assertEqual(registered["name"], "kanban_task_claimed")
        callback = registered["callback"]
        add_subscription(self.conn, self.task_id, "whatsapp", "notify+wake")
        self.assertTrue(kb.unblock_task(self.conn, self.task_id))

        def fire(event_name, task_id, **kwargs):
            events.append("claim")
            self.assertEqual(event_name, "kanban_task_claimed")
            events.append("policy")
            callback(task_id=task_id, db_path=self.db_path, **kwargs)

        def spawn(task, workspace, board=None):
            events.append("spawn")
            self.assertEqual(
                modes_by_platform(self.conn, task.id)["whatsapp"], "wake"
            )
            return None

        with (
            patch.object(kb, "_fire_kanban_lifecycle_hook", side_effect=fire),
            patch("hermes_cli.profiles.profile_exists", return_value=True),
            patch.object(kb, "_memory_pressure_level", return_value="normal"),
        ):
            result = kb.dispatch_once(
                self.conn,
                spawn_fn=spawn,
                board="default",
                reconcile_orphans=False,
            )

        self.assertEqual(events, ["claim", "policy", "spawn"])
        self.assertEqual(len(result.spawned), 1)

    def test_installed_watcher_maps_wake_to_active_only(self):
        source_path = Path(inspect.getsourcefile(kanban_watchers) or "")
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        expressions: dict[str, ast.expr] = {}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in {
                    "wake_agent",
                    "send_passive",
                }:
                    expressions.setdefault(target.id, node.value)

        self.assertEqual(set(expressions), {"wake_agent", "send_passive"})
        actual = {
            name: eval(
                compile(ast.Expression(expr), str(source_path), "eval"),
                {},
                {"mode": "wake"},
            )
            for name, expr in expressions.items()
        }
        self.assertEqual(actual, {"wake_agent": True, "send_passive": False})


if __name__ == "__main__":
    unittest.main()
