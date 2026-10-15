#!/usr/bin/env python3
"""agents/ 의 에이전트 원본을 검증하고 Claude Code가 읽는 위치로 동기화한다.

사용법:
  python3 scripts/sync_agents.py                  # 이 저장소에 동기화
  python3 scripts/sync_agents.py --check          # 검증만 (변경 없음, 결과가 다르면 실패)
  python3 scripts/sync_agents.py --target ~/my-app  # 다른 프로젝트에 설치
  python3 scripts/sync_agents.py --target ~       # 모든 프로젝트에서 쓰도록 사용자 폴더에 설치

동기화 결과:
  <target>/.claude/agents/<name>.md   Claude Code용 에이전트 파일 (대시보드용 필드 제거)
  <target>/.claude/agent-office.md     운영 규칙 (office/ORCHESTRATION.md 복사본)
  registry.json                         대시보드용 에이전트 목록 (이 저장소에만 생성)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CLAUDE_FIELDS = ("name", "description", "tools", "model", "color")
OFFICE_FIELDS = ("department", "tier")
REQUIRED_FIELDS = ("name", "description", "model", "department", "tier")
TIERS = ("lead", "specialist")
MODELS = ("haiku", "sonnet", "opus", "inherit")
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

MANIFEST_NAME = ".agent-office-manifest.json"
ORCHESTRATION_MARKER = "<!-- agent-office: 자동 생성 파일. office/ORCHESTRATION.md 를 고친 뒤 sync 하세요 -->"


class AgentError(Exception):
    pass


@dataclass
class Agent:
    meta: dict[str, str]
    body: str
    source: Path

    @property
    def name(self) -> str:
        return self.meta["name"]

    def render(self) -> str:
        lines = ["---"]
        lines += [f"{key}: {self.meta[key]}" for key in CLAUDE_FIELDS if key in self.meta]
        lines.append("---")
        return "\n".join(lines) + "\n" + self.body


def parse_agent(path: Path) -> Agent:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not match:
        raise AgentError(f"{path}: 맨 위에 --- 로 둘러싼 frontmatter가 없습니다")

    meta: dict[str, str] = {}
    for lineno, line in enumerate(match.group(1).splitlines(), start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = stripped.partition(":")
        key = key.strip()
        if not sep:
            raise AgentError(f"{path}:{lineno}: 'key: value' 형식이 아닙니다")
        if key not in CLAUDE_FIELDS + OFFICE_FIELDS:
            raise AgentError(f"{path}:{lineno}: 알 수 없는 필드 '{key}'")
        if key in meta:
            raise AgentError(f"{path}:{lineno}: '{key}' 필드가 중복됩니다")
        meta[key] = value.strip()

    return Agent(meta=meta, body=match.group(2), source=path)


def validate(agent: Agent, departments: dict[str, dict]) -> None:
    path, meta = agent.source, agent.meta
    for key in REQUIRED_FIELDS:
        if not meta.get(key):
            raise AgentError(f"{path}: 필수 필드 '{key}'가 비어 있습니다")
    if not NAME_RE.match(meta["name"]):
        raise AgentError(f"{path}: name은 영문 소문자와 하이픈만 씁니다 (예: code-reviewer)")
    if meta["name"] != path.stem:
        raise AgentError(f"{path}: name '{meta['name']}'과 파일 이름 '{path.stem}'이 다릅니다")
    if meta["department"] not in departments:
        raise AgentError(f"{path}: 등록되지 않은 부서 '{meta['department']}' (config/departments.json 확인)")
    if meta["department"] != path.parent.name:
        raise AgentError(f"{path}: department '{meta['department']}'와 폴더 '{path.parent.name}'가 다릅니다")
    if meta["tier"] not in TIERS:
        raise AgentError(f"{path}: tier는 {', '.join(TIERS)} 중 하나여야 합니다")
    if meta["model"] not in MODELS:
        raise AgentError(f"{path}: model은 {', '.join(MODELS)} 중 하나여야 합니다")
    if not agent.body.strip():
        raise AgentError(f"{path}: 지시문(본문)이 비어 있습니다")


def load_departments(path: Path) -> dict[str, dict]:
    items = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"]: item for item in items}


def load_agents(agents_dir: Path, departments: dict[str, dict]) -> list[Agent]:
    agents = [parse_agent(path) for path in sorted(agents_dir.glob("*/*.md"))]
    for agent in agents:
        validate(agent, departments)

    seen: dict[str, Path] = {}
    for agent in agents:
        if agent.name in seen:
            raise AgentError(f"에이전트 이름 '{agent.name}'이 중복됩니다: {seen[agent.name]}, {agent.source}")
        seen[agent.name] = agent.source

    for dept_id in departments:
        leads = [a.name for a in agents if a.meta["department"] == dept_id and a.meta["tier"] == "lead"]
        members = [a for a in agents if a.meta["department"] == dept_id]
        if members and len(leads) != 1:
            raise AgentError(f"부서 '{dept_id}'에는 팀장(tier: lead)이 정확히 한 명 있어야 합니다 (현재 {len(leads)}명)")

    order = {dept_id: dept["order"] for dept_id, dept in departments.items()}
    agents.sort(key=lambda a: (order[a.meta["department"]], a.meta["tier"] != "lead", a.name))
    return agents


def build_registry(agents: list[Agent], departments: dict[str, dict], root: Path) -> str:
    registry = {
        "departments": sorted(departments.values(), key=lambda d: d["order"]),
        "agents": [
            {
                "name": a.name,
                "department": a.meta["department"],
                "tier": a.meta["tier"],
                "model": a.meta["model"],
                "tools": [t.strip() for t in a.meta.get("tools", "").split(",") if t.strip()],
                "description": a.meta["description"],
                "source": a.source.relative_to(root).as_posix(),
            }
            for a in agents
        ],
    }
    return json.dumps(registry, ensure_ascii=False, indent=2) + "\n"


def planned_files(agents: list[Agent], orchestration: str, target: Path) -> dict[Path, str]:
    claude_dir = target / ".claude"
    files = {claude_dir / "agents" / f"{a.name}.md": a.render() for a in agents}
    files[claude_dir / "agent-office.md"] = f"{ORCHESTRATION_MARKER}\n{orchestration}"
    return files


def is_managed(path: Path, managed_names: set[str]) -> bool:
    if path.name == "agent-office.md":
        return path.read_text(encoding="utf-8").startswith(ORCHESTRATION_MARKER)
    return path.stem in managed_names


def sync(agents: list[Agent], orchestration: str, target: Path, force: bool = False) -> list[str]:
    """target에 파일을 쓰고, 이전에 이 스크립트가 만들었지만 이제 없는 에이전트를 지운다."""
    agents_dir = target / ".claude" / "agents"
    manifest_path = agents_dir / MANIFEST_NAME
    previous = set(json.loads(manifest_path.read_text(encoding="utf-8"))) if manifest_path.exists() else set()

    files = planned_files(agents, orchestration, target)
    conflicts = [p for p in files if p.exists() and not is_managed(p, previous)]
    if conflicts and not force:
        names = "\n  ".join(str(p) for p in conflicts)
        raise AgentError(f"직접 만든 파일로 보여 덮어쓰지 않았습니다 (--force로 덮어쓰기):\n  {names}")

    log = []
    agents_dir.mkdir(parents=True, exist_ok=True)
    for path, content in files.items():
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
            log.append(f"갱신 {path}")

    current = {a.name for a in agents}
    for name in sorted(previous - current):
        stale = agents_dir / f"{name}.md"
        if stale.exists():
            stale.unlink()
            log.append(f"삭제 {stale}")

    manifest_path.write_text(json.dumps(sorted(current), indent=2) + "\n", encoding="utf-8")
    return log


def check(agents: list[Agent], orchestration: str, registry: str, root: Path) -> list[str]:
    """동기화 결과가 저장소에 커밋된 파일과 같은지 확인한다."""
    expected = planned_files(agents, orchestration, root)
    expected[root / "registry.json"] = registry
    problems = []
    for path, content in expected.items():
        if not path.exists():
            problems.append(f"없음 {path}")
        elif path.read_text(encoding="utf-8") != content:
            problems.append(f"다름 {path}")

    agents_dir = root / ".claude" / "agents"
    current = {a.name for a in agents}
    manifest_path = agents_dir / MANIFEST_NAME
    previous = set(json.loads(manifest_path.read_text(encoding="utf-8"))) if manifest_path.exists() else set()
    for name in sorted(previous - current):
        if (agents_dir / f"{name}.md").exists():
            problems.append(f"남은 파일 {agents_dir / f'{name}.md'}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", type=Path, help="에이전트를 설치할 프로젝트 폴더 (기본: 이 저장소)")
    parser.add_argument("--check", action="store_true", help="검증만 하고 파일은 바꾸지 않는다")
    parser.add_argument("--force", action="store_true", help="직접 만든 같은 이름의 파일도 덮어쓴다")
    args = parser.parse_args(argv)

    try:
        departments = load_departments(ROOT / "config" / "departments.json")
        agents = load_agents(ROOT / "agents", departments)
        orchestration = (ROOT / "office" / "ORCHESTRATION.md").read_text(encoding="utf-8")
        registry = build_registry(agents, departments, ROOT)

        if args.check:
            problems = check(agents, orchestration, registry, ROOT)
            if problems:
                print("동기화가 필요합니다. python3 scripts/sync_agents.py 를 실행하세요:")
                print("\n".join(f"  {p}" for p in problems))
                return 1
            print(f"검증 통과: 에이전트 {len(agents)}개, 부서 {len(departments)}개")
            return 0

        target = (args.target or ROOT).expanduser().resolve()
        log = sync(agents, orchestration, target, force=args.force)
        if target == ROOT:
            (ROOT / "registry.json").write_text(registry, encoding="utf-8")
    except AgentError as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1

    print("\n".join(log) or "변경 없음")
    print(f"완료: 에이전트 {len(agents)}개 → {target / '.claude' / 'agents'}")
    if target == Path.home().resolve():
        print("운영 규칙을 쓰려면 ~/.claude/CLAUDE.md에 다음 한 줄을 추가하세요:")
        print("  @~/.claude/agent-office.md")
    elif target != ROOT:
        print("운영 규칙을 쓰려면 그 프로젝트의 CLAUDE.md에 다음 한 줄을 추가하세요:")
        print("  @.claude/agent-office.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
