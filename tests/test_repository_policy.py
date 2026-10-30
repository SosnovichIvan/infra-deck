import importlib.util
from pathlib import Path
import unittest
import json
import os
import subprocess
import sys
import textwrap

spec = importlib.util.spec_from_file_location("repository_policy", Path(__file__).resolve().parents[1] / "scripts/check_repository.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class BranchPolicyTests(unittest.TestCase):
    def event(self, head, base, source="SosnovichIvan/infra-deck"):
        return {"pull_request": {"head": {"ref": head, "repo": {"full_name": source}}, "base": {"ref": base}}}

    def test_working_branch_to_develop(self):
        policy.branch_policy(self.event("codex/topic", "develop"), "SosnovichIvan/infra-deck")

    def test_external_contribution_to_develop(self):
        policy.branch_policy(self.event("fix", "develop", "contributor/fork"), "SosnovichIvan/infra-deck")

    def test_release_from_own_develop(self):
        policy.branch_policy(self.event("develop", "main"), "SosnovichIvan/infra-deck")

    def test_wrong_branch_routes_fail(self):
        for head, base, source in [("feature", "main", "SosnovichIvan/infra-deck"),
                                   ("main", "develop", "SosnovichIvan/infra-deck"),
                                   ("develop", "main", "contributor/fork"),
                                   ("feature", "unknown", "SosnovichIvan/infra-deck")]:
            with self.subTest(head=head, base=base, source=source), self.assertRaises(ValueError):
                policy.branch_policy(self.event(head, base, source), "SosnovichIvan/infra-deck")

    def test_missing_metadata_fails(self):
        with self.assertRaises(ValueError):
            policy.branch_policy({}, "SosnovichIvan/infra-deck")

    def test_new_runtime_cannot_use_bootstrap_checks(self):
        for path in ["apps/unknown/package.json", "services/agent/main.py", "infra/compose.yaml", "unknown.go"]:
            with self.subTest(path=path):
                self.assertTrue(policy.inventory_errors([path]))

    def test_bootstrap_inventory(self):
        self.assertEqual(policy.inventory_errors(["README.md", "docs/product.md", ".github/workflows/pull-request.yml"]), [])


class AggregateGateTests(unittest.TestCase):
    def run_gate(self, results):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/pull-request.yml").read_text()
        code = textwrap.dedent(workflow.split("python3 - <<'PYTHON'\n")[1].split("          PYTHON")[0])
        return subprocess.run([sys.executable, "-c", code], env={**os.environ, "RESULTS": json.dumps(results)}, capture_output=True).returncode

    def test_only_full_success_is_accepted(self):
        good = {name: {"result": "success"} for name in ("branch-policy", "repository", "workflows", "backend", "frontend", "e2e", "production-smoke")}
        self.assertEqual(self.run_gate(good), 0)
        for name in good:
            for status in ("failure", "cancelled", "skipped", "unknown"):
                with self.subTest(job=name, status=status):
                    bad = {**good, name: {"result": status}}
                    self.assertNotEqual(self.run_gate(bad), 0)
        self.assertNotEqual(self.run_gate({}), 0)
        self.assertNotEqual(self.run_gate({"repository": {"result": "success"}}), 0)


class CoveragePolicyTests(unittest.TestCase):
    def test_lines_and_branches_are_independently_required(self):
        import tempfile
        root=Path(__file__).resolve().parents[1]
        for lines,branches,expected in [(100,100,0),(89,100,1),(100,89,1),(0,0,1)]:
            with tempfile.TemporaryDirectory() as directory:
                report=Path(directory)/'coverage.json'
                report.write_text(json.dumps({'totals':{'covered_lines':lines,
                    'num_statements':100,'covered_branches':branches,'num_branches':100}}))
                result=subprocess.run([sys.executable,str(root/'scripts/check_coverage.py'),
                    str(report)],capture_output=True)
                self.assertEqual(bool(result.returncode),bool(expected))
