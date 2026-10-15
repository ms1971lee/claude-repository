import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sync_agents as sa  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEPARTMENTS = {
    "dev": {"id": "dev", "name": "개발팀", "order": 1, "description": ""},
    "qa": {"id": "qa", "name": "품질관리팀", "order": 2, "description": ""},
}


def agent_text(name, department="dev", tier="specialist", extra=""):
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {name} 설명\n"
        "tools: Read, Grep\n"
        "model: sonnet\n"
        f"department: {department}\n"
        f"tier: {tier}\n"
        f"{extra}"
        "---\n"
        "지시문\n"
    )


class SyncAgentsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.agents_dir = self.dir / "agents"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = self.agents_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_team(self):
        self.write("dev/dev-lead.md", agent_text("dev-lead", tier="lead"))
        self.write("dev/architect.md", agent_text("architect"))

    def test_repository_agents_are_valid_and_in_sync(self):
        departments = sa.load_departments(ROOT / "config" / "departments.json")
        agents = sa.load_agents(ROOT / "agents", departments)
        orchestration = (ROOT / "office" / "ORCHESTRATION.md").read_text(encoding="utf-8")
        registry = sa.build_registry(agents, departments, ROOT)
        self.assertEqual(sa.check(agents, orchestration, registry, ROOT), [])

    def test_lead_sorts_first_and_office_fields_are_stripped(self):
        self.write_team()
        agents = sa.load_agents(self.agents_dir, DEPARTMENTS)
        self.assertEqual([a.name for a in agents], ["dev-lead", "architect"])
        rendered = agents[1].render()
        self.assertIn("name: architect\n", rendered)
        self.assertNotIn("department", rendered)
        self.assertNotIn("tier", rendered)
        self.assertTrue(rendered.endswith("지시문\n"))

    def test_rejects_name_that_differs_from_filename(self):
        self.write("dev/dev-lead.md", agent_text("dev-lead", tier="lead"))
        self.write("dev/architect.md", agent_text("architekt"))
        with self.assertRaisesRegex(sa.AgentError, "파일 이름"):
            sa.load_agents(self.agents_dir, DEPARTMENTS)

    def test_rejects_unknown_field(self):
        self.write("dev/dev-lead.md", agent_text("dev-lead", tier="lead", extra="modle: opus\n"))
        with self.assertRaisesRegex(sa.AgentError, "알 수 없는 필드 'modle'"):
            sa.load_agents(self.agents_dir, DEPARTMENTS)

    def test_rejects_department_folder_mismatch(self):
        self.write("dev/dev-lead.md", agent_text("dev-lead", tier="lead"))
        self.write("dev/tester.md", agent_text("tester", department="qa"))
        with self.assertRaisesRegex(sa.AgentError, "폴더"):
            sa.load_agents(self.agents_dir, DEPARTMENTS)

    def test_requires_exactly_one_lead_per_department(self):
        self.write("dev/architect.md", agent_text("architect"))
        with self.assertRaisesRegex(sa.AgentError, "팀장"):
            sa.load_agents(self.agents_dir, DEPARTMENTS)

    def test_sync_writes_files_and_removes_stale_managed_agents(self):
        self.write_team()
        target = self.dir / "project"
        agents = sa.load_agents(self.agents_dir, DEPARTMENTS)
        sa.sync(agents, "규칙\n", target)

        out = target / ".claude" / "agents"
        self.assertTrue((out / "architect.md").exists())
        self.assertTrue((target / ".claude" / "agent-office.md").read_text(encoding="utf-8").endswith("규칙\n"))
        self.assertEqual(json.loads((out / sa.MANIFEST_NAME).read_text()), ["architect", "dev-lead"])

        (self.agents_dir / "dev" / "architect.md").unlink()
        sa.sync(sa.load_agents(self.agents_dir, DEPARTMENTS), "규칙\n", target)
        self.assertFalse((out / "architect.md").exists())

    def test_sync_keeps_user_files_and_refuses_to_overwrite_them(self):
        self.write_team()
        target = self.dir / "project"
        out = target / ".claude" / "agents"
        out.mkdir(parents=True)
        (out / "my-own.md").write_text("mine", encoding="utf-8")
        (out / "architect.md").write_text("hand written", encoding="utf-8")

        agents = sa.load_agents(self.agents_dir, DEPARTMENTS)
        with self.assertRaisesRegex(sa.AgentError, "덮어쓰지 않았습니다"):
            sa.sync(agents, "규칙\n", target)
        self.assertEqual((out / "architect.md").read_text(encoding="utf-8"), "hand written")

        sa.sync(agents, "규칙\n", target, force=True)
        self.assertEqual((out / "my-own.md").read_text(encoding="utf-8"), "mine")
        self.assertIn("name: architect", (out / "architect.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
