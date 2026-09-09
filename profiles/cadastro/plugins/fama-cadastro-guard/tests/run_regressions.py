"""Run shared business fixtures against THIS installed profile plugin, offline."""
import importlib.util
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
shared = root.parents[3] / "ops/plugins/fama-cadastro-guard/tests"
sys.path.insert(0, str(shared))
import test_guard
spec = importlib.util.spec_from_file_location("profile_guard_under_test", root / "__init__.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
test_guard.guard = module
test_guard.ROOT = root
import test_runtime
suite = unittest.TestSuite([
    unittest.defaultTestLoader.loadTestsFromModule(test_guard),
    unittest.defaultTestLoader.loadTestsFromModule(test_runtime),
    unittest.defaultTestLoader.discover(str(root / "tests")),
])
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(not result.wasSuccessful())
