# AI 에이전트 사무실

이 저장소는 역할별 AI 에이전트(직원)와 그 운영 규칙, 대시보드를 만드는 프로젝트다. 설계는 `docs/DESIGN.md`를 따른다.

@.claude/agent-office.md

## 저장소 작업 규칙

- 에이전트 원본은 `agents/<부서>/<이름>.md`에서만 고친다. `.claude/agents/`, `.claude/agent-office.md`, `registry.json`은 자동 생성 파일이다
- 원본이나 `office/ORCHESTRATION.md`를 고친 뒤에는 `python3 scripts/sync_agents.py`를 실행하고 결과물도 함께 커밋한다
- 커밋 전 확인: `python3 scripts/sync_agents.py --check` 와 `python3 -m unittest discover -s tests`
- 부서 추가는 `config/departments.json`에 등록한 뒤 같은 id의 폴더를 만든다. 부서마다 팀장(tier: lead)은 한 명이다
