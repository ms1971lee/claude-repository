# AI 에이전트 사무실

역할별 AI 에이전트(직원)에게 일을 나눠 맡기고, 누가 일하는지와 비용을 대시보드로 보는 시스템입니다. Claude Code의 서브에이전트 기능 위에서 동작합니다.

설계: [docs/DESIGN.md](docs/DESIGN.md) · 운영 규칙: [office/ORCHESTRATION.md](office/ORCHESTRATION.md)

## 조직 (6개 팀, 18명)

| 팀 | 팀장 | 전문가 |
|---|---|---|
| 기획팀 | planning-lead | product-planner, requirements-analyst |
| 디자인팀 | design-lead | ux-designer, visual-designer |
| UIUX개발팀 | uiux-lead | frontend-developer, accessibility-specialist |
| 개발팀 | dev-lead | architect, backend-developer |
| 품질관리팀 | qa-lead | test-engineer, code-reviewer |
| 검증팀 | verification-lead | acceptance-verifier, security-auditor |

## 시작하기

준비물: [Claude Code](https://code.claude.com/docs), Python 3.9 이상, Git

```bash
git clone https://github.com/ms1971lee/claude-repository.git
cd claude-repository
claude
```

Claude Code 안에서 이렇게 요청해 보세요.

```
할 일 관리 웹앱을 만들고 싶어. 기획팀부터 시작해줘.
```

메인 AI가 사무실 매니저가 되어 기획팀장에게 작업 지시서를 받고, 기획 전문가들에게 일을 나눠 맡깁니다. 결과물은 `workspace/<작업명>/`에 쌓입니다. `/agents` 명령으로 등록된 에이전트 목록을 볼 수 있습니다.

## 다른 프로젝트에서 쓰기

```bash
# 특정 프로젝트에 설치
python3 scripts/sync_agents.py --target ~/projects/my-app

# 모든 프로젝트에서 쓰도록 사용자 폴더에 설치
python3 scripts/sync_agents.py --target ~
```

설치 후 안내대로 그 프로젝트의 `CLAUDE.md`에 `@.claude/agent-office.md` 한 줄을 추가하면 운영 규칙도 함께 적용됩니다.

## 에이전트 추가하고 고치기

1. `agents/<부서>/<이름>.md`를 만들거나 고칩니다. 형식은 기존 파일을 참고하세요
2. `python3 scripts/sync_agents.py`를 실행합니다. 형식 오류가 있으면 알려줍니다
3. 생성된 `.claude/agents/`, `registry.json`까지 함께 커밋합니다

```bash
python3 scripts/sync_agents.py --check        # 동기화 상태 확인
python3 -m unittest discover -s tests         # 테스트
```

## 폴더 구조

```
agents/<부서>/        에이전트 원본 (여기만 고친다)
config/               부서 목록
office/               운영 규칙 원본
scripts/              동기화 스크립트
.claude/agents/       Claude Code용 에이전트 (자동 생성)
registry.json         대시보드용 목록 (자동 생성)
workspace/            에이전트 작업 결과물
docs/                 설계 문서
```

## 로드맵

- [x] 1단계: 첫 직원 채용 (에이전트 18명, 동기화 스크립트)
- [ ] 2단계: 출근부 (hooks로 실행 기록, 토큰 비용 집계)
- [ ] 3단계: 상황실 (대시보드)
- [ ] 4단계: 야간 근무 (예약 작업, 예산 제한)
- [ ] 5단계: 확장
