# InsightFlow - AI 기술 트래킹 앱 구축 계획

## TL;DR

> **Quick Summary**: GitHub Actions 기반 서버리스 AI 기술 뉴스 트래커. GeekNews + Hacker News에서 기사를 수집하고, Gemini 2.0 Flash로 키워드 필터링 + 3줄 요약을 생성한 뒤, 텔레그램 봇으로 일일 다이제스트를 발송합니다. 데이터는 JSON 파일 + GitHub Issues에 저장됩니다.
>
> **Deliverables**:
> - 시스템 아키텍처 설계도 (Mermaid 다이어그램 포함 README)
> - GitHub Actions 워크플로우 YAML (`daily-digest.yml`)
> - 모듈화된 Python 소스 코드 (6개 모듈)
> - 로컬 테스트 환경 구성 가이드
> - 중복 수집 방지 로직 + 실패 알림 메커니즘
>
> **Estimated Effort**: Medium (~2-3일 구현)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8

---

## Context

### Original Request
개발자용 AI 기술 트래킹 앱 구축. 단순한 코딩을 넘어 전체 인프라 설계와 배포 파이프라인을 포함하는 가이드. VPS 없이 GitHub Actions만으로 매일 오전 8시 자동 실행. RSS/API 데이터 수집 → LLM 요약 → 텔레그램 발송.

### Interview Summary
**Key Discussions**:
- Python 3.11 선택 (안정성 + 호환성)
- Gemini 2.0 Flash 단독 사용 (무료 티어: RPM 15, RPD 1,500)
- 하이브리드 필터링: 키워드 화이트리스트 1차 → Gemini 2차 관련성 판단
- JSON + GitHub Issues 병행 저장
- 텔레그램 봇으로 일일 단일 메시지 발송
- GeekNews + Hacker News 2개 소스만 (확장 가능 설계)
- 테스트 없음 (Agent QA 검증)
- 관심 키워드: 풀스택 + 인프라 (AI, LLM, React, TypeScript, Rust, Go, Docker, K8s, DevOps 등)

**Research Findings**:
- GitHub Actions cron `0 23 * * *` = KST 오전 8시 (±5-15분 편차 가능)
- Gemini 무료 티어 2025.12 대폭 축소됨 (gemini-2.0-flash: RPD 1,500)
- GeekNews Atom 피드: `https://news.hada.io/rss/news` (NOT `/rss` - 403 발생)
- HN API: `https://hacker-news.firebaseio.com/v0/` (배치 미지원, 개별 fetch 필요)
- 참조 프로젝트: `aastroza/rss-feeds-scraper` (GitHub Actions + JSON 자동커밋 패턴)

### Metis Review
**Identified Gaps** (addressed):
- **GeekNews RSS URL 오류**: `/rss` → `/rss/news`로 수정 (403 방지)
- **GeekNews 원본 URL 미포함**: Atom 피드에 원본 기사 URL 없음 → 토픽 페이지 파싱으로 해결
- **Telegram 4,096 char 제한**: 메시지 청킹 로직 추가
- **Gemini 배칭 필수**: 1,500 RPD 내에서 처리하려면 5-10건씩 배치 호출
- **JSON 파일 증가 문제**: 날짜별 분리 저장으로 해결
- **Git push 레이스 컨디션**: `concurrency` 그룹으로 동시 실행 방지
- **HN API 순차 호출 느림**: `asyncio` + `aiohttp`로 병렬 fetch

---

## Work Objectives

### Core Objective
GitHub Actions 크론 스케줄로 매일 자동 실행되는 AI 기술 뉴스 수집 + 요약 + 텔레그램 발송 파이프라인을 구축한다.

### Concrete Deliverables
- `src/config.py` - 설정값 및 환경변수 관리
- `src/scraper.py` - GeekNews Atom 피드 + HN API 데이터 수집
- `src/ai_handler.py` - Gemini 2.0 Flash 배치 요약 + 관련성 점수
- `src/storage.py` - JSON 저장 + 중복 방지 + GitHub Issues 생성
- `src/notifier.py` - 텔레그램 메시지 포매팅 + 청킹 + 발송
- `src/main.py` - 메인 오케스트레이터 (--dry-run 지원)
- `.github/workflows/daily-digest.yml` - GitHub Actions 워크플로우
- `README.md` - 아키텍처 다이어그램 + 설정 가이드 + 로컬 테스트 방법
- `.env.example` - 환경변수 템플릿
- `requirements.txt` - 의존성 목록

### Definition of Done
- [x] `python src/main.py --dry-run` 로컬에서 에러 없이 실행됨
- [x] GeekNews + HN에서 기사 수집되고 JSON에 저장됨
- [x] 중복 실행 시 데이터가 중복되지 않음
- [x] 텔레그램으로 포매팅된 다이제스트 메시지 수신됨
- [x] GitHub Actions 워크플로우가 유효한 YAML임
- [x] GitHub Actions에서 실행 실패 시 텔레그램 알림 발송됨

### Must Have
- 매일 오전 8시 KST 자동 실행
- GeekNews + HN 데이터 수집
- 키워드 1차 필터 + Gemini 2차 관련성 판단
- 3줄 요약 생성
- 텔레그램 일일 다이제스트 발송
- JSON 데이터 저장 + Git 자동 커밋
- 주요 기사 GitHub Issues 생성
- 중복 수집 방지 (seen_ids 기반)
- 실패 시 텔레그램 알림
- --dry-run 모드 (로컬 테스트용)
- Gemini 배치 호출 (RPD 절약)

### Must NOT Have (Guardrails)
- ❌ 플러그인/어댑터 아키텍처 (소스 확장용 추상 레이어 금지 - GeekNews + HN 하드코딩)
- ❌ YAML/TOML 설정 파일 파서 (Python 상수 + .env만 사용)
- ❌ 커스텀 예외 클래스 (내장 예외 + 간단한 try/except만)
- ❌ Pydantic 또는 무거운 검증 라이브러리 (dataclass 또는 TypedDict까지만)
- ❌ 재시도 라이브러리 (tenacity 등) - 간단한 loop 기반 재시도만
- ❌ 웹 UI, 대시보드, 관리자 패널
- ❌ SQLite, ORM, 추상 스토리지 레이어
- ❌ Reddit, Dev.to 등 추가 소스
- ❌ 주간/월간 다이제스트 집계
- ❌ 기사 본문 전체 스크래핑
- ❌ 감성 분석, 카테고리 분류, 번역

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.
> ALL verification is executed by the agent using tools (Bash, Playwright, interactive_bash, curl, etc.). No exceptions.

### Test Decision
- **Infrastructure exists**: NO (새 프로젝트)
- **Automated tests**: None (Agent-Executed QA만)
- **Framework**: None

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

> QA scenarios are the PRIMARY verification method.
> The executing agent DIRECTLY verifies each deliverable by running it.

**Verification Tool by Deliverable Type:**

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| Python 모듈 | Bash (python) | Import, 함수 호출, 출력 검증 |
| GitHub Actions YAML | Bash (python yaml.safe_load) | YAML 파싱 검증 |
| 텔레그램 발송 | Bash (curl) | Bot API 직접 호출 후 응답 확인 |
| 전체 파이프라인 | Bash (python main.py) | --dry-run 실행 후 출력/파일 검증 |

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: 프로젝트 초기 설정 (config, requirements, .env)
└── Task 2: 시스템 아키텍처 설계도 (README.md with Mermaid)

Wave 2 (After Wave 1):
├── Task 3: 데이터 수집 모듈 (scraper.py)
├── Task 4: AI 처리 모듈 (ai_handler.py)
└── Task 5: 데이터 저장 모듈 (storage.py)

Wave 3 (After Wave 2):
├── Task 6: 알림 모듈 (notifier.py)
└── Task 7: 메인 오케스트레이터 (main.py)

Wave 4 (After Wave 3):
└── Task 8: GitHub Actions 워크플로우 + 최종 통합 테스트

Critical Path: Task 1 → Task 3 → Task 7 → Task 8
Parallel Speedup: ~35% faster than sequential
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 3, 4, 5, 6, 7 | 2 |
| 2 | None | 8 | 1 |
| 3 | 1 | 7 | 4, 5 |
| 4 | 1 | 7 | 3, 5 |
| 5 | 1 | 7 | 3, 4 |
| 6 | 1 | 7 | 3, 4, 5 |
| 7 | 3, 4, 5, 6 | 8 | None |
| 8 | 2, 7 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2 | task(category="quick") + task(category="writing") |
| 2 | 3, 4, 5 | 3x task(category="unspecified-high") in parallel |
| 3 | 6, 7 | task(category="unspecified-high") sequential (7 depends on 6) |
| 4 | 8 | task(category="deep") for final integration |

---

## TODOs

- [x] 1. 프로젝트 초기 설정 및 설정 모듈

  **What to do**:
  - `requirements.txt` 생성 (의존성 목록):
    ```
    feedparser>=6.0.0
    aiohttp>=3.9.0
    google-generativeai>=0.8.0
    python-dotenv>=1.0.0
    requests>=2.31.0
    ```
  - `.env.example` 생성 (환경변수 템플릿):
    ```
    GEMINI_API_KEY=your_gemini_api_key_here
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
    TELEGRAM_CHAT_ID=your_chat_id_here
    DRY_RUN=false
    ```
  - `src/__init__.py` 빈 파일 생성
  - `src/config.py` 구현:
    - `python-dotenv`로 .env 로딩
    - 모든 상수 정의 (키워드 목록, API URL, 배치 크기 등)
    - 키워드 목록: `["AI", "LLM", "GPT", "Gemini", "Claude", "transformer", "deep learning", "machine learning", "React", "TypeScript", "Rust", "Go", "Docker", "Kubernetes", "K8s", "DevOps", "CI/CD", "microservice", "API", "database", "PostgreSQL", "Redis", "cloud", "AWS", "GCP", "Azure", "serverless", "인공지능", "딥러닝", "머신러닝"]`
    - GeekNews Atom URL: `https://news.hada.io/rss/news`
    - HN API base: `https://hacker-news.firebaseio.com/v0/`
    - Gemini model: `gemini-2.0-flash`
    - 배치 크기: 8 (articles per Gemini call)
    - HN fetch 개수: 30 (top stories 중)
    - Gemini 관련성 점수 임계값: 0.6 (0~1)
    - Issues 생성 점수 임계값: 0.8
  - `data/` 디렉토리에 `.gitkeep` 생성

  **Must NOT do**:
  - YAML/TOML 설정 파일 파서 사용 금지
  - Pydantic 사용 금지
  - 설정 클래스 상속 구조 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 단순 파일 생성과 상수 정의. 복잡한 로직 없음.
  - **Skills**: []
    - 별도 스킬 불필요
  - **Skills Evaluated but Omitted**:
    - `dev-workflow`: 테스트 없으므로 TDD 워크플로우 불필요

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Tasks 3, 4, 5, 6, 7
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - 없음 (새 프로젝트)

  **API/Type References**:
  - 없음

  **External References**:
  - `feedparser` 공식: https://feedparser.readthedocs.io/
  - `google-generativeai` PyPI: https://pypi.org/project/google-generativeai/
  - `python-dotenv` 공식: https://github.com/theskumar/python-dotenv
  - Gemini 무료 티어 제한 참조: gemini-2.0-flash RPM 15, RPD 1,500 (2026.02 기준)

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: requirements.txt가 유효하고 설치 가능
    Tool: Bash
    Preconditions: Python 3.11 사용 가능
    Steps:
      1. pip install -r requirements.txt --dry-run 2>&1
      2. Assert: 출력에 "ERROR" 없음
      3. Assert: feedparser, aiohttp, google-generativeai, python-dotenv, requests 모두 포함
    Expected Result: 모든 패키지가 설치 가능 상태
    Evidence: 명령 출력 캡처

  Scenario: config.py가 올바르게 로드됨
    Tool: Bash (python)
    Preconditions: .env.example → .env로 복사됨
    Steps:
      1. cp .env.example .env
      2. python -c "from src.config import KEYWORDS, GEEKNEWS_RSS_URL, HN_API_BASE, GEMINI_MODEL, BATCH_SIZE; print(f'Keywords: {len(KEYWORDS)}, URL: {GEEKNEWS_RSS_URL}, HN: {HN_API_BASE}, Model: {GEMINI_MODEL}, Batch: {BATCH_SIZE}')"
      3. Assert: Keywords >= 25
      4. Assert: GEEKNEWS_RSS_URL == "https://news.hada.io/rss/news"
      5. Assert: GEMINI_MODEL == "gemini-2.0-flash"
      6. Assert: BATCH_SIZE == 8
    Expected Result: 모든 설정값이 올바르게 로드됨
    Evidence: python 출력 캡처

  Scenario: .env.example에 모든 필수 변수 포함
    Tool: Bash
    Steps:
      1. grep -c "GEMINI_API_KEY" .env.example
      2. grep -c "TELEGRAM_BOT_TOKEN" .env.example
      3. grep -c "TELEGRAM_CHAT_ID" .env.example
      4. grep -c "DRY_RUN" .env.example
      5. Assert: 모두 1 이상
    Expected Result: 4개 필수 환경변수 템플릿 존재
    Evidence: grep 출력 캡처
  ```

  **Commit**: YES
  - Message: `feat(config): add project setup with config module and dependencies`
  - Files: `requirements.txt`, `.env.example`, `src/__init__.py`, `src/config.py`, `data/.gitkeep`
  - Pre-commit: `python -c "from src.config import KEYWORDS; print('OK')"`

---

- [x] 2. 시스템 아키텍처 설계도 (README.md)

  **What to do**:
  - `README.md` 작성:
    - 프로젝트 소개 (InsightFlow - AI 기술 트래킹)
    - Mermaid 다이어그램으로 시스템 아키텍처 표현:
      ```mermaid
      graph TD
        A[GitHub Actions Cron - 08:00 KST] --> B[scraper.py]
        B --> B1[GeekNews Atom Feed]
        B --> B2[Hacker News API]
        B1 --> C[storage.py - Dedup Check]
        B2 --> C
        C --> D[config.py - Keyword Filter]
        D --> E[ai_handler.py - Gemini Batch]
        E --> F[notifier.py - Telegram]
        E --> G[storage.py - JSON Save]
        G --> H[Git Auto-Commit]
        G --> I[GitHub Issues - Notable Articles]
        F --> J[Daily Digest Message]
      ```
    - 데이터 흐름 설명 (한국어)
    - 모듈별 역할 설명
    - 로컬 개발 환경 설정 가이드:
      1. 레포 클론
      2. Python 3.11 + venv 생성
      3. `pip install -r requirements.txt`
      4. `.env.example` → `.env` 복사 후 실제 키 입력
      5. `python src/main.py --dry-run` 실행
    - GitHub Actions 설정 가이드:
      1. GitHub Secrets 설정 (GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
      2. Actions 탭에서 워크플로우 활성화
      3. 수동 실행 테스트 (workflow_dispatch)
    - 텔레그램 봇 설정 방법:
      1. @BotFather로 봇 생성
      2. 봇 토큰 획득
      3. chat_id 확인 방법
    - Gemini API 키 발급 방법 (Google AI Studio)
    - 실패 시 알림 동작 설명
    - 중복 방지 메커니즘 설명

  **Must NOT do**:
  - 영어로 작성 금지 (한국어 프로젝트)
  - 과도한 뱃지/이미지 추가 금지
  - 기여 가이드/CoC 추가 금지 (개인 프로젝트)

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 문서 작성 중심 작업. Mermaid 다이어그램 + 가이드 작성.
  - **Skills**: [`doc-writer`]
    - `doc-writer`: 문서 구조화와 명확한 기술 문서 작성에 특화
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: 문서 작성이므로 UI 스킬 불필요

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 8
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `aastroza/rss-feeds-scraper` (https://github.com/aastroza/rss-feeds-scraper) - GitHub Actions + RSS + JSON 자동커밋 프로젝트 구조 참고

  **Documentation References**:
  - Mermaid 공식 문법: https://mermaid.js.org/syntax/flowchart.html
  - GitHub Actions 스케줄 트리거: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
  - Telegram BotFather: https://core.telegram.org/bots#botfather
  - Google AI Studio: https://aistudio.google.com/

  **WHY Each Reference Matters**:
  - aastroza 프로젝트: 유사한 아키텍처로 실제 운영 중인 프로젝트. README 구조 참고.
  - Mermaid: 아키텍처 다이어그램 작성에 필요한 문법

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: README.md가 유효하고 핵심 섹션 포함
    Tool: Bash
    Steps:
      1. test -f README.md && echo "EXISTS"
      2. Assert: "EXISTS" 출력
      3. grep -c "mermaid" README.md
      4. Assert: >= 1 (Mermaid 다이어그램 포함)
      5. grep -c "로컬" README.md
      6. Assert: >= 1 (로컬 개발 가이드 포함)
      7. grep -c "GitHub Actions" README.md
      8. Assert: >= 1
      9. grep -c "텔레그램" README.md
      10. Assert: >= 1
    Expected Result: README에 아키텍처, 로컬 가이드, Actions, 텔레그램 섹션 존재
    Evidence: grep 출력 캡처
  ```

  **Commit**: YES
  - Message: `docs: add README with architecture diagram and setup guide`
  - Files: `README.md`
  - Pre-commit: `test -f README.md`

---

- [x] 3. 데이터 수집 모듈 (scraper.py)

  **What to do**:
  - `src/scraper.py` 구현:
    - `@dataclass Article` 정의:
      - `source: str` ("geeknews" | "hackernews")
      - `source_id: str` (GeekNews topic ID | HN item ID)
      - `title: str`
      - `url: str` (원본 기사 URL)
      - `discussion_url: str` (GeekNews/HN 토론 페이지 URL)
      - `summary: str` (GeekNews 기존 요약 또는 빈 문자열)
      - `score: int` (HN 점수 또는 0)
      - `published_at: str` (ISO 8601)
      - `ai_summary: str = ""` (Gemini가 채울 필드)
      - `relevance_score: float = 0.0` (Gemini가 채울 필드)

    - `fetch_geeknews() -> list[Article]`:
      - `feedparser.parse("https://news.hada.io/rss/news")` 호출
      - **중요**: User-Agent 헤더 설정 (GitHub Actions에서 403 방지)
      - Atom 피드 파싱: `entry.title`, `entry.link` (토론 페이지), `entry.id`, `entry.content[0].value` (한국어 요약)
      - **원본 URL 추출**: GeekNews Atom 피드에는 원본 URL이 없음. 각 토픽 페이지(`https://news.hada.io/topic?id=XXXXX`)를 requests로 fetch하여 원본 URL을 파싱하거나, `entry.link`을 discussion_url로 사용하고 `entry.content`의 첫 번째 링크를 원본 URL로 추출
      - 실패 시 빈 리스트 반환 + 에러 로깅
      - `<published>` 날짜로 최근 24시간 기사만 필터링

    - `fetch_hackernews(count: int = 30) -> list[Article]`:
      - `aiohttp` 사용한 비동기 fetch
      - Step 1: `/v0/topstories.json` → 상위 `count`개 ID 추출
      - Step 2: `asyncio.gather()`로 `/v0/item/{id}.json` 병렬 fetch (30개 동시)
      - 각 아이템에서 `title`, `url` (없으면 self-post), `score`, `time` 추출
      - `discussion_url`: `https://news.ycombinator.com/item?id={id}`
      - self-post (url 없음)는 `discussion_url`을 `url`로 사용
      - 실패한 개별 아이템은 skip + 에러 로깅
      - 전체 fetch 실패 시 빈 리스트 반환

    - `scrape_all() -> list[Article]`:
      - `fetch_geeknews()` + `fetch_hackernews()` 호출
      - 두 결과 합쳐서 반환
      - 각 소스 실패는 독립적 (하나 실패해도 다른 소스 결과는 반환)

  **Must NOT do**:
  - 추상 Source 클래스/인터페이스 생성 금지
  - 다른 소스 지원 코드 금지
  - 기사 본문 전체 스크래핑 금지
  - BeautifulSoup 과도한 사용 금지 (피드 파싱은 feedparser로)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Atom 피드 파싱 + 비동기 HTTP + 원본 URL 추출 등 중간 복잡도. 여러 외부 API와 상호작용.
  - **Skills**: []
    - 별도 스킬 불필요 (표준 Python 작업)
  - **Skills Evaluated but Omitted**:
    - `dev-workflow`: 테스트 없으므로 불필요

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5)
  - **Blocks**: Task 7
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/config.py` (Task 1에서 생성) - `GEEKNEWS_RSS_URL`, `HN_API_BASE`, `HN_TOP_N` 상수 사용

  **API/Type References**:
  - GeekNews Atom Feed: `https://news.hada.io/rss/news` - Atom 형식 (`xmlns='http://www.w3.org/2005/Atom'`)
    - `<entry>` 하위: `<title>` (CDATA Korean), `<link rel='alternate' href='...'>` (토론 페이지), `<id>`, `<published>` (ISO 8601 +09:00), `<content type='html'>` (한국어 요약)
    - **주의**: `<link>`는 원본 URL이 아닌 GeekNews 토론 페이지 URL
  - HN API: `https://hacker-news.firebaseio.com/v0/`
    - `/topstories.json` → `int[]` (최대 500개)
    - `/item/{id}.json` → `{id, by, title, url?, score, time, descendants, type}`
    - `url`이 없으면 self-post (Ask HN, Show HN 등)

  **External References**:
  - feedparser 공식 문서: https://feedparser.readthedocs.io/en/latest/
    - Atom 피드도 RSS와 동일한 인터페이스로 파싱 (`feed.entries`, `entry.title`, `entry.link`)
  - aiohttp 공식: https://docs.aiohttp.org/en/stable/
  - HN API 공식: https://github.com/HackerNews/API

  **WHY Each Reference Matters**:
  - GeekNews Atom 구조를 정확히 알아야 올바른 필드를 추출할 수 있음 (특히 원본 URL 누락 문제)
  - HN API는 배치 미지원이므로 aiohttp 비동기 패턴이 필수
  - feedparser는 Atom/RSS 모두 처리하므로 통일된 인터페이스 사용 가능

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: GeekNews Atom 피드 수집 성공
    Tool: Bash (python)
    Preconditions: requirements.txt 설치됨, 인터넷 연결됨
    Steps:
      1. pip install -r requirements.txt
      2. python -c "
         from src.scraper import fetch_geeknews
         articles = fetch_geeknews()
         print(f'Count: {len(articles)}')
         if articles:
             a = articles[0]
             print(f'Title: {a.title[:50]}')
             print(f'Source: {a.source}')
             print(f'URL: {a.url}')
             print(f'Discussion: {a.discussion_url}')
             print(f'Has summary: {bool(a.summary)}')
         "
      3. Assert: Count > 0
      4. Assert: Source == "geeknews"
      5. Assert: URL은 빈 문자열이 아님 (원본 URL 또는 토론 URL)
      6. Assert: Discussion URL에 "news.hada.io" 포함
    Expected Result: GeekNews에서 최소 1개 이상의 기사 수집
    Evidence: python 출력 캡처

  Scenario: Hacker News API 수집 성공
    Tool: Bash (python)
    Preconditions: requirements.txt 설치됨, 인터넷 연결됨
    Steps:
      1. python -c "
         import asyncio
         from src.scraper import fetch_hackernews
         articles = asyncio.run(fetch_hackernews(count=5))
         print(f'Count: {len(articles)}')
         if articles:
             a = articles[0]
             print(f'Title: {a.title[:50]}')
             print(f'Source: {a.source}')
             print(f'Score: {a.score}')
             print(f'URL: {a.url}')
         "
      2. Assert: Count >= 3 (5개 중 최소 3개는 성공해야 함)
      3. Assert: Source == "hackernews"
      4. Assert: Score > 0
    Expected Result: HN에서 최소 3개 이상의 기사 수집
    Evidence: python 출력 캡처

  Scenario: scrape_all이 두 소스를 합쳐서 반환
    Tool: Bash (python)
    Steps:
      1. python -c "
         from src.scraper import scrape_all
         articles = scrape_all()
         sources = set(a.source for a in articles)
         print(f'Total: {len(articles)}')
         print(f'Sources: {sources}')
         "
      2. Assert: Total > 0
      3. Assert: sources에 "geeknews" 또는 "hackernews" 중 최소 1개 포함
    Expected Result: 두 소스에서 수집된 기사 목록 반환
    Evidence: python 출력 캡처

  Scenario: 네트워크 실패 시 빈 리스트 반환 (graceful degradation)
    Tool: Bash (python)
    Steps:
      1. python -c "
         import feedparser
         # 잘못된 URL로 테스트
         result = feedparser.parse('https://invalid-url-that-does-not-exist.example.com/rss')
         print(f'Entries: {len(result.entries)}')
         print(f'Bozo: {result.bozo}')
         "
      2. Assert: Entries == 0
      3. Assert: 에러 없이 실행 완료됨 (exit code 0)
    Expected Result: 잘못된 URL에도 크래시 없이 빈 결과 반환
    Evidence: python 출력 캡처
  ```

  **Commit**: YES
  - Message: `feat(scraper): add GeekNews Atom feed and HN API data collection`
  - Files: `src/scraper.py`
  - Pre-commit: `python -c "from src.scraper import scrape_all; print('OK')"`

---

- [x] 4. AI 처리 모듈 (ai_handler.py)

  **What to do**:
  - `src/ai_handler.py` 구현:
    - `keyword_filter(articles: list[Article]) -> list[Article]`:
      - `config.KEYWORDS` 리스트를 사용하여 1차 필터링
      - 각 기사의 `title` + `summary`에서 키워드 매칭 (대소문자 무시)
      - 매칭된 기사만 반환 (Gemini API 호출 최소화)
      - 한국어 키워드도 포함 (`인공지능`, `딥러닝` 등)

    - `batch_summarize(articles: list[Article]) -> list[Article]`:
      - `google.generativeai` SDK 사용
      - `GEMINI_API_KEY`로 인증
      - 기사를 `config.BATCH_SIZE` (8개)씩 그룹으로 나눔
      - 각 배치에 대해 Gemini 호출:
        - **프롬프트 설계**:
          ```
          다음 기술 기사들을 분석해주세요. 각 기사에 대해:
          1. 개발자 관련성 점수 (0.0~1.0)
          2. 한국어로 3줄 핵심 요약

          기사 목록:
          [1] 제목: {title}
              요약: {summary}
          [2] ...

          JSON 형식으로 응답해주세요:
          [{"index": 1, "relevance": 0.85, "summary": "..."}, ...]
          ```
        - JSON 응답 파싱하여 각 Article의 `ai_summary`, `relevance_score` 업데이트
      - Rate limit 대응: 배치 간 2초 대기 (`time.sleep(2)`)
      - 429 에러 시 3회 재시도 (지수 백오프: 5s, 15s, 45s)
      - 전체 Gemini 실패 시 graceful degradation: 키워드 필터 결과만 반환 (AI 요약 없이)

    - `filter_and_summarize(articles: list[Article]) -> list[Article]`:
      - Step 1: `keyword_filter(articles)` → 키워드 매칭된 기사
      - Step 2: `batch_summarize(filtered)` → AI 요약 + 관련성 점수 추가
      - Step 3: `relevance_score >= config.RELEVANCE_THRESHOLD` (0.6) 이상만 최종 반환
      - `relevance_score >= config.ISSUE_THRESHOLD` (0.8) 기사에 `notable` 플래그

  **Must NOT do**:
  - Pydantic 모델 사용 금지
  - tenacity 라이브러리 사용 금지 (간단한 루프 재시도만)
  - 커스텀 예외 클래스 생성 금지
  - 프롬프트 템플릿 엔진 사용 금지 (f-string만)
  - 감성 분석, 카테고리 분류 등 추가 AI 기능 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Gemini API 통합, 배치 처리 로직, 에러 핸들링, JSON 파싱 등 중간-높은 복잡도
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `ultrabrain`: API 통합은 복잡하지만 로직 자체는 직관적

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 5)
  - **Blocks**: Task 7
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/config.py` (Task 1) - KEYWORDS, GEMINI_API_KEY, GEMINI_MODEL, BATCH_SIZE, RELEVANCE_THRESHOLD
  - `src/scraper.py:Article` (Task 3) - Article dataclass 구조

  **API/Type References**:
  - Gemini Python SDK: `google.generativeai`
    - `genai.configure(api_key=...)` → 초기화
    - `model = genai.GenerativeModel('gemini-2.0-flash')` → 모델 생성
    - `response = model.generate_content(prompt)` → 응답 생성
    - `response.text` → 텍스트 응답
  - 무료 티어 제한: RPM 15, RPD 1,500 (2026.02 기준)
  - JSON 응답 모드: `generation_config=genai.GenerationConfig(response_mime_type="application/json")`

  **External References**:
  - google-generativeai 퀵스타트: https://ai.google.dev/gemini-api/docs/quickstart
  - Gemini 무료 티어 제한: https://ai.google.dev/gemini-api/docs/rate-limits

  **WHY Each Reference Matters**:
  - Gemini SDK 사용법을 정확히 알아야 올바른 API 호출 가능
  - 무료 티어 제한을 이해해야 배치 크기와 대기 시간 최적화 가능
  - JSON 응답 모드를 사용하면 응답 파싱이 안정적

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: 키워드 필터링이 올바르게 동작
    Tool: Bash (python)
    Preconditions: src/scraper.py의 Article dataclass 사용 가능
    Steps:
      1. python -c "
         from src.scraper import Article
         from src.ai_handler import keyword_filter
         articles = [
             Article(source='test', source_id='1', title='New AI Model Released', url='http://a.com', discussion_url='', summary='', score=0, published_at=''),
             Article(source='test', source_id='2', title='Cooking Recipe Today', url='http://b.com', discussion_url='', summary='', score=0, published_at=''),
             Article(source='test', source_id='3', title='Docker Container Best Practices', url='http://c.com', discussion_url='', summary='', score=0, published_at=''),
         ]
         filtered = keyword_filter(articles)
         print(f'Input: {len(articles)}, Filtered: {len(filtered)}')
         titles = [a.title for a in filtered]
         print(f'Titles: {titles}')
         "
      2. Assert: Filtered == 2 (AI + Docker 기사만)
      3. Assert: "Cooking Recipe" 기사가 필터링됨
    Expected Result: 키워드 포함 기사만 통과
    Evidence: python 출력 캡처

  Scenario: Gemini 배치 요약 성공 (실제 API 호출)
    Tool: Bash (python)
    Preconditions: .env에 유효한 GEMINI_API_KEY 설정됨
    Steps:
      1. python -c "
         from src.scraper import Article
         from src.ai_handler import batch_summarize
         articles = [
             Article(source='test', source_id='1', title='OpenAI Releases GPT-5', url='http://a.com', discussion_url='', summary='OpenAI released GPT-5 with improved reasoning capabilities', score=100, published_at='2026-02-10'),
         ]
         result = batch_summarize(articles)
         if result:
             a = result[0]
             print(f'AI Summary: {a.ai_summary[:100]}')
             print(f'Relevance: {a.relevance_score}')
             print(f'Has summary: {bool(a.ai_summary)}')
         else:
             print('EMPTY - Gemini may have failed')
         "
      2. Assert: Has summary == True
      3. Assert: 0.0 <= Relevance <= 1.0
    Expected Result: Gemini가 요약과 관련성 점수 반환
    Evidence: python 출력 캡처

  Scenario: Gemini 실패 시 graceful degradation
    Tool: Bash (python)
    Preconditions: 잘못된 API 키 사용
    Steps:
      1. GEMINI_API_KEY=invalid_key python -c "
         from src.scraper import Article
         from src.ai_handler import filter_and_summarize
         articles = [
             Article(source='test', source_id='1', title='AI Model Test', url='http://a.com', discussion_url='', summary='Test summary', score=0, published_at=''),
         ]
         result = filter_and_summarize(articles)
         print(f'Count: {len(result)}')
         print(f'Has AI summary: {bool(result[0].ai_summary) if result else False}')
         " 2>&1
      2. Assert: 프로그램이 크래시하지 않음 (exit code 0)
      3. Assert: Count >= 0 (빈 리스트 또는 AI 요약 없는 기사 반환)
    Expected Result: Gemini 실패해도 크래시 없이 키워드 필터 결과 반환
    Evidence: python 출력 캡처
  ```

  **Commit**: YES
  - Message: `feat(ai): add Gemini batch summarization with keyword filtering`
  - Files: `src/ai_handler.py`
  - Pre-commit: `python -c "from src.ai_handler import filter_and_summarize; print('OK')"`

---

- [x] 5. 데이터 저장 모듈 (storage.py)

  **What to do**:
  - `src/storage.py` 구현:
    - `load_seen_ids() -> set[str]`:
      - `data/seen_ids.json` 파일에서 이전에 처리된 기사 ID 세트 로드
      - 파일 없으면 빈 set 반환
      - 키 형식: `"{source}:{source_id}"` (예: `"geeknews:12345"`, `"hackernews:67890"`)

    - `save_seen_ids(seen_ids: set[str])`:
      - `data/seen_ids.json`에 JSON 배열로 저장
      - 정렬하여 저장 (git diff 최소화)

    - `filter_new_articles(articles: list[Article], seen_ids: set[str]) -> list[Article]`:
      - 각 기사의 `"{source}:{source_id}"`가 seen_ids에 없는 것만 반환
      - 새 기사의 ID를 seen_ids에 추가

    - `save_daily_articles(articles: list[Article], date_str: str)`:
      - `data/{YYYY}/{MM}/{DD}.json` 경로에 저장
      - 디렉토리 자동 생성 (`os.makedirs(exist_ok=True)`)
      - 기사를 dict 리스트로 변환하여 JSON 저장 (indent=2, ensure_ascii=False)
      - 이미 파일 존재 시 기존 데이터에 추가 (append)

    - `create_github_issues(articles: list[Article])`:
      - `relevance_score >= config.ISSUE_THRESHOLD` (0.8) 이상인 기사만
      - GitHub API (`GITHUB_TOKEN` 환경변수) 사용
      - Issue 제목: `[{source}] {title}`
      - Issue 본문:
        ```
        ## 기사 정보
        - **원본 URL**: {url}
        - **토론**: {discussion_url}
        - **소스**: {source}
        - **관련성 점수**: {relevance_score}

        ## AI 요약
        {ai_summary}
        ```
      - 라벨: `source:{source}`, `auto-collected`
      - 하루 최대 5개 Issue 생성 (GitHub API 부하 방지)
      - dry-run 모드에서는 스킵

  **Must NOT do**:
  - SQLite, ORM 사용 금지
  - 추상 스토리지 레이어 금지
  - 전체 이력을 단일 파일에 저장 금지 (날짜별 분리 필수)
  - 복잡한 인덱싱/검색 로직 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 파일 I/O, JSON 처리, GitHub API 통합, 중복 방지 로직
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `git-master`: git 작업은 GitHub Actions에서 수행하므로 직접적 관련 없음

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 4)
  - **Blocks**: Task 7
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/config.py` (Task 1) - ISSUE_THRESHOLD, data 디렉토리 경로
  - `src/scraper.py:Article` (Task 3) - Article dataclass 구조

  **API/Type References**:
  - GitHub REST API - Issues: `POST /repos/{owner}/{repo}/issues`
    - Headers: `Authorization: Bearer {GITHUB_TOKEN}`, `Accept: application/vnd.github.v3+json`
    - Body: `{"title": "...", "body": "...", "labels": [...]}`
  - `GITHUB_TOKEN`: GitHub Actions에서 자동 제공 (`${{ secrets.GITHUB_TOKEN }}`)
  - `GITHUB_REPOSITORY`: 환경변수로 `owner/repo` 형식 자동 제공

  **External References**:
  - GitHub REST API Issues: https://docs.github.com/en/rest/issues/issues#create-an-issue

  **WHY Each Reference Matters**:
  - GitHub Issues API를 올바르게 호출하려면 인증 방식과 엔드포인트를 정확히 알아야 함
  - `GITHUB_TOKEN`과 `GITHUB_REPOSITORY` 환경변수는 Actions에서 자동 제공됨을 알아야 함

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: 중복 방지 (seen_ids) 동작 확인
    Tool: Bash (python)
    Preconditions: data/ 디렉토리 존재
    Steps:
      1. python -c "
         from src.storage import load_seen_ids, save_seen_ids, filter_new_articles
         from src.scraper import Article
         # 초기 상태: 빈 seen_ids
         seen = load_seen_ids()
         print(f'Initial seen: {len(seen)}')
         
         articles = [
             Article(source='test', source_id='1', title='A', url='', discussion_url='', summary='', score=0, published_at=''),
             Article(source='test', source_id='2', title='B', url='', discussion_url='', summary='', score=0, published_at=''),
         ]
         new = filter_new_articles(articles, seen)
         print(f'First run new: {len(new)}')
         save_seen_ids(seen)
         
         # 동일 기사로 재실행
         seen2 = load_seen_ids()
         new2 = filter_new_articles(articles, seen2)
         print(f'Second run new: {len(new2)}')
         "
      2. Assert: Initial seen == 0
      3. Assert: First run new == 2
      4. Assert: Second run new == 0 (중복 제거됨)
    Expected Result: 같은 기사를 두 번 처리하면 두 번째에는 새 기사가 0개
    Evidence: python 출력 캡처

  Scenario: 일일 기사 JSON 저장 확인
    Tool: Bash (python)
    Preconditions: data/ 디렉토리 존재
    Steps:
      1. python -c "
         import json, os
         from src.storage import save_daily_articles
         from src.scraper import Article
         articles = [
             Article(source='test', source_id='99', title='Test Article', url='http://test.com', discussion_url='', summary='Test', score=10, published_at='2026-02-10'),
         ]
         save_daily_articles(articles, '2026-02-10')
         path = 'data/2026/02/10.json'
         assert os.path.exists(path), f'{path} not found'
         data = json.load(open(path))
         print(f'Articles saved: {len(data)}')
         print(f'Title: {data[0][\"title\"]}')
         "
      2. Assert: Articles saved == 1
      3. Assert: Title == "Test Article"
      4. 정리: rm -rf data/2026
    Expected Result: 날짜별 디렉토리에 JSON 파일 저장됨
    Evidence: python 출력 캡처

  Scenario: seen_ids.json 정렬 저장 확인
    Tool: Bash
    Steps:
      1. python -c "
         from src.storage import save_seen_ids
         save_seen_ids({'test:3', 'test:1', 'test:2'})
         "
      2. python -c "import json; data = json.load(open('data/seen_ids.json')); print(data)"
      3. Assert: 출력이 정렬된 리스트 ['test:1', 'test:2', 'test:3']
    Expected Result: seen_ids가 정렬되어 저장됨 (git diff 최소화)
    Evidence: python 출력 캡처
  ```

  **Commit**: YES
  - Message: `feat(storage): add JSON storage, deduplication, and GitHub Issues creation`
  - Files: `src/storage.py`
  - Pre-commit: `python -c "from src.storage import load_seen_ids; print('OK')"`

---

- [x] 6. 알림 모듈 (notifier.py)

  **What to do**:
  - `src/notifier.py` 구현:
    - `format_digest(articles: list[Article]) -> str`:
      - 텔레그램 MarkdownV2 형식으로 다이제스트 포매팅
      - 헤더: `📰 InsightFlow Daily Digest - {날짜}`
      - 소스별 섹션:
        ```
        🇰🇷 *GeekNews*
        
        1\. *{title}*
        {ai_summary 또는 기존 summary}
        🔗 [원문]({url}) \| [토론]({discussion_url})
        ⭐ 관련성: {relevance_score}
        
        🌍 *Hacker News*
        
        1\. *{title}* \(⬆{score}\)
        {ai_summary}
        🔗 [원문]({url}) \| [토론]({discussion_url})
        ```
      - 기사가 없으면: `오늘은 관련 기사가 없습니다.`
      - MarkdownV2 특수문자 이스케이프 처리 (`_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`)

    - `chunk_message(text: str, max_length: int = 4096) -> list[str]`:
      - 4,096 UTF-8 문자 제한에 맞게 메시지 분할
      - 기사 단위로 분할 (기사 중간에서 자르지 않음)
      - 각 청크 끝에 `(1/N)` 형식 페이지 표시

    - `send_telegram(text: str)`:
      - `requests.post()` 사용 (간단한 HTTP POST)
      - URL: `https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage`
      - Body: `{"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "MarkdownV2"}`
      - 3회 재시도 (지수 백오프: 2s, 6s, 18s)
      - 에러 시 로깅 + 예외 전파 (main에서 처리)

    - `send_digest(articles: list[Article])`:
      - `format_digest()` → `chunk_message()` → 각 청크에 `send_telegram()` 호출
      - 청크 간 1초 대기 (rate limit 방지)

    - `send_failure_notification(error_message: str)`:
      - 실패 알림 전용 함수
      - `⚠️ InsightFlow 실행 실패\n\n{error_message}\n\n{timestamp}`
      - MarkdownV2 이스케이프 적용

  **Must NOT do**:
  - python-telegram-bot 라이브러리 사용 금지 (간단한 requests로 충분)
  - 인라인 키보드/버튼 추가 금지
  - 이미지/미디어 첨부 금지
  - HTML 파싱 모드 사용 금지 (MarkdownV2 통일)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 텔레그램 API 통합, MarkdownV2 이스케이프 처리, 메시지 청킹 로직
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: 텔레그램 메시지 포매팅이지 UI가 아님

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential, before Task 7)
  - **Blocks**: Task 7
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/config.py` (Task 1) - TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  - `src/scraper.py:Article` (Task 3) - Article dataclass 구조

  **API/Type References**:
  - Telegram Bot API - sendMessage:
    - `POST https://api.telegram.org/bot{token}/sendMessage`
    - Body: `{"chat_id": "...", "text": "...", "parse_mode": "MarkdownV2"}`
    - 성공 응답: `{"ok": true, "result": {...}}`
    - 에러 응답: `{"ok": false, "error_code": 400, "description": "..."}`
  - MarkdownV2 이스케이프 필요 문자: `_*[]()~` `` ` `` `>#+\-=|{}.!`
  - 메시지 최대 길이: UTF-8 4,096자

  **External References**:
  - Telegram Bot API sendMessage: https://core.telegram.org/bots/api#sendmessage
  - MarkdownV2 형식: https://core.telegram.org/bots/api#markdownv2-style

  **WHY Each Reference Matters**:
  - MarkdownV2 이스케이프가 까다로움 - 공식 문서에서 정확한 규칙 확인 필수
  - 4,096자 제한 초과 시 API 에러 발생하므로 청킹 로직이 핵심

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: 다이제스트 포매팅 + 길이 제한 확인
    Tool: Bash (python)
    Steps:
      1. python -c "
         from src.scraper import Article
         from src.notifier import format_digest, chunk_message
         articles = [
             Article(source='geeknews', source_id='1', title='AI 기술 트렌드', url='http://a.com', discussion_url='http://d.com', summary='요약 테스트', score=0, published_at='2026-02-10', ai_summary='AI 요약 결과입니다.', relevance_score=0.9),
         ]
         digest = format_digest(articles)
         print(f'Digest length: {len(digest)}')
         print(f'Contains InsightFlow: {\"InsightFlow\" in digest}')
         chunks = chunk_message(digest)
         print(f'Chunks: {len(chunks)}')
         for i, c in enumerate(chunks):
             print(f'Chunk {i} length: {len(c)}')
             assert len(c) <= 4096, f'Chunk {i} exceeds 4096 chars'
         "
      2. Assert: Digest length > 0
      3. Assert: Contains InsightFlow == True
      4. Assert: 모든 청크 <= 4096자
    Expected Result: 다이제스트가 올바르게 포매팅되고 청크 분할됨
    Evidence: python 출력 캡처

  Scenario: 텔레그램 발송 성공 (실제 API)
    Tool: Bash (python)
    Preconditions: .env에 유효한 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 설정됨
    Steps:
      1. python -c "
         from src.notifier import send_telegram
         send_telegram('🧪 InsightFlow 테스트 메시지입니다\\.')
         print('SENT')
         "
      2. Assert: "SENT" 출력 (에러 없음)
      3. Assert: 텔레그램에서 메시지 수신 확인 (send_telegram 반환값 체크)
    Expected Result: 텔레그램으로 테스트 메시지 발송됨
    Evidence: python 출력 캡처

  Scenario: MarkdownV2 특수문자 이스케이프 확인
    Tool: Bash (python)
    Steps:
      1. python -c "
         from src.notifier import format_digest
         from src.scraper import Article
         # 특수문자 포함 제목
         articles = [
             Article(source='hackernews', source_id='1', title='C++ vs Rust: A 2026 Guide (Part 1)', url='http://a.com', discussion_url='http://d.com', summary='', score=150, published_at='2026-02-10', ai_summary='C++과 Rust 비교.', relevance_score=0.7),
         ]
         digest = format_digest(articles)
         # MarkdownV2에서 파싱 에러를 발생시키는 이스케이프되지 않은 문자가 없어야 함
         print(f'Contains raw +: {\"+\" in digest and \"\\\\+\" not in digest}')
         print(f'Contains raw .: {\".\" in digest and \"\\\\.\" not in digest}')
         print('Format check passed')
         "
      2. Assert: 이스케이프 처리된 텍스트 생성됨
    Expected Result: 특수문자가 MarkdownV2 규격에 맞게 이스케이프됨
    Evidence: python 출력 캡처

  Scenario: 실패 알림 발송
    Tool: Bash (python)
    Preconditions: .env에 유효한 텔레그램 설정
    Steps:
      1. python -c "
         from src.notifier import send_failure_notification
         send_failure_notification('Test error: API connection timeout')
         print('FAILURE NOTIFICATION SENT')
         "
      2. Assert: "FAILURE NOTIFICATION SENT" 출력
    Expected Result: 실패 알림이 텔레그램으로 발송됨
    Evidence: python 출력 캡처
  ```

  **Commit**: YES
  - Message: `feat(notifier): add Telegram digest formatting with message chunking`
  - Files: `src/notifier.py`
  - Pre-commit: `python -c "from src.notifier import send_digest; print('OK')"`

---

- [x] 7. 메인 오케스트레이터 (main.py)

  **What to do**:
  - `src/main.py` 구현:
    - CLI 인터페이스:
      - `--dry-run` 플래그: 텔레그램 발송 + git 커밋 + GitHub Issues 스킵
      - `argparse` 사용 (간단한 인자 파싱)

    - `main()` 함수 - 전체 파이프라인 오케스트레이션:
      ```python
      def main(dry_run: bool = False):
          try:
              # 1. 데이터 수집
              logger.info("Starting data collection...")
              all_articles = scrape_all()
              logger.info(f"Collected {len(all_articles)} articles")
              
              # 2. 중복 제거
              seen_ids = load_seen_ids()
              new_articles = filter_new_articles(all_articles, seen_ids)
              logger.info(f"New articles: {len(new_articles)}")
              
              if not new_articles:
                  logger.info("No new articles found. Exiting.")
                  return
              
              # 3. 키워드 필터 + AI 요약
              processed = filter_and_summarize(new_articles)
              logger.info(f"After filtering: {len(processed)} articles")
              
              # 4. 데이터 저장
              today = datetime.now().strftime("%Y-%m-%d")
              save_daily_articles(processed, today)
              save_seen_ids(seen_ids)
              
              # 5. 텔레그램 발송
              if not dry_run:
                  send_digest(processed)
                  logger.info("Telegram digest sent")
              else:
                  logger.info("[DRY RUN] Telegram send skipped")
              
              # 6. GitHub Issues 생성
              if not dry_run:
                  create_github_issues(processed)
                  logger.info("GitHub Issues created")
              
              logger.info("Pipeline completed successfully")
              
          except Exception as e:
              logger.error(f"Pipeline failed: {e}")
              if not dry_run:
                  try:
                      send_failure_notification(str(e))
                  except:
                      logger.error("Failed to send failure notification")
              raise
      ```

    - `logging` 설정:
      - 포맷: `[%(asctime)s] %(levelname)s - %(message)s`
      - 레벨: INFO (기본), DEBUG (환경변수로 전환 가능)
      - stdout으로 출력 (GitHub Actions 로그에 표시)

    - `if __name__ == "__main__"` 블록:
      - argparse로 `--dry-run` 파싱
      - 환경변수 `DRY_RUN=true`도 지원
      - `main(dry_run=...)` 호출

  **Must NOT do**:
  - click/typer 등 CLI 라이브러리 사용 금지 (argparse만)
  - 복잡한 로깅 설정 금지 (기본 logging만)
  - 스케줄러 라이브러리 사용 금지 (GitHub Actions가 스케줄링)
  - 데몬/서비스 모드 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 모든 모듈을 통합하는 오케스트레이션 로직. 에러 핸들링 + 로깅 + CLI.
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `deep`: 통합 작업이지만 각 모듈이 이미 완성되어 있으므로 deep 불필요

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (after Task 6)
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 3, 4, 5, 6

  **References**:

  **Pattern References**:
  - `src/scraper.py:scrape_all` (Task 3) - 데이터 수집 함수
  - `src/ai_handler.py:filter_and_summarize` (Task 4) - AI 필터링/요약 함수
  - `src/storage.py:load_seen_ids, filter_new_articles, save_seen_ids, save_daily_articles, create_github_issues` (Task 5) - 저장/중복방지 함수들
  - `src/notifier.py:send_digest, send_failure_notification` (Task 6) - 알림 함수들

  **WHY Each Reference Matters**:
  - main.py는 모든 모듈을 호출하는 오케스트레이터이므로 각 모듈의 공개 인터페이스를 정확히 알아야 함
  - 에러 핸들링 흐름이 중요: 어떤 단계에서 실패해도 이후 단계를 적절히 처리해야 함

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: --dry-run 모드 전체 파이프라인 실행
    Tool: Bash (python)
    Preconditions: .env에 유효한 GEMINI_API_KEY 설정 (텔레그램은 필수 아님)
    Steps:
      1. python src/main.py --dry-run 2>&1
      2. Assert: exit code 0
      3. Assert: 출력에 "Starting data collection" 포함
      4. Assert: 출력에 "DRY RUN" 포함
      5. Assert: 출력에 "Pipeline completed" 또는 "No new articles" 포함
      6. Assert: 텔레그램 메시지가 발송되지 않았음 (DRY RUN 로그)
    Expected Result: 전체 파이프라인이 dry-run으로 에러 없이 실행됨
    Evidence: 전체 stdout/stderr 캡처

  Scenario: DRY_RUN 환경변수로도 dry-run 동작
    Tool: Bash
    Steps:
      1. DRY_RUN=true python src/main.py 2>&1
      2. Assert: 출력에 "DRY RUN" 포함
    Expected Result: 환경변수로도 dry-run 모드 활성화됨
    Evidence: stdout 캡처

  Scenario: 두 번 연속 실행 시 중복 없음
    Tool: Bash
    Preconditions: data/seen_ids.json 없거나 비어있음
    Steps:
      1. rm -f data/seen_ids.json
      2. python src/main.py --dry-run 2>&1
      3. COUNT1=$(python -c "import json; print(len(json.load(open('data/seen_ids.json'))))")
      4. python src/main.py --dry-run 2>&1
      5. Assert: 두 번째 실행 출력에 "No new articles" 포함 또는 새 기사 수가 0
    Expected Result: 동일 기사가 중복 처리되지 않음
    Evidence: 두 실행의 stdout 캡처

  Scenario: 실패 시 에러 로깅 확인
    Tool: Bash
    Steps:
      1. GEMINI_API_KEY=invalid python src/main.py --dry-run 2>&1
      2. Assert: 프로그램이 완료됨 (graceful degradation) 또는 에러 로그 출력
    Expected Result: 실패해도 적절한 에러 메시지와 함께 종료
    Evidence: stderr 캡처
  ```

  **Commit**: YES
  - Message: `feat(main): add pipeline orchestrator with dry-run support`
  - Files: `src/main.py`
  - Pre-commit: `python src/main.py --dry-run 2>&1 | head -5`

---

- [x] 8. GitHub Actions 워크플로우 + 최종 통합

  **What to do**:
  - `.github/workflows/daily-digest.yml` 생성:
    ```yaml
    name: InsightFlow Daily Digest

    on:
      schedule:
        - cron: '0 23 * * *'  # 매일 KST 08:00 (UTC 23:00)
      workflow_dispatch:  # 수동 트리거 지원

    concurrency:
      group: daily-digest
      cancel-in-progress: false  # 진행 중인 실행 취소하지 않음

    permissions:
      contents: write  # JSON 파일 커밋용
      issues: write    # GitHub Issues 생성용

    jobs:
      run-digest:
        runs-on: ubuntu-latest
        
        steps:
          - name: Checkout Repository
            uses: actions/checkout@v4
            with:
              token: ${{ secrets.GITHUB_TOKEN }}

          - name: Set up Python 3.11
            uses: actions/setup-python@v5
            with:
              python-version: '3.11'
              cache: 'pip'

          - name: Install Dependencies
            run: pip install -r requirements.txt

          - name: Run InsightFlow Pipeline
            env:
              GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
              TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
              TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
              GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
            run: python src/main.py

          - name: Commit Updated Data
            run: |
              git config user.name "InsightFlow Bot"
              git config user.email "insightflow-bot@users.noreply.github.com"
              git add data/
              git diff --staged --quiet || git commit -m "data: daily digest $(date +%Y-%m-%d)"
              git push

          - name: Notify on Failure
            if: failure()
            env:
              TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
              TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
            run: |
              python -c "
              from src.notifier import send_failure_notification
              send_failure_notification('GitHub Actions workflow failed. Check: https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}')
              "
    ```

  - 최종 통합 검증:
    - 모든 모듈 import 테스트
    - YAML 문법 검증
    - 파일 구조 확인
    - `--dry-run` 전체 파이프라인 실행

  **Must NOT do**:
  - Docker 컨테이너 사용 금지 (직접 Python 실행이 빠름)
  - 복잡한 캐싱 전략 금지 (pip 캐시만)
  - 다른 워크플로우 파일 생성 금지 (단일 워크플로우)
  - main 브랜치 외 배포 전략 금지

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: GitHub Actions YAML + 최종 통합 테스트. 모든 모듈이 올바르게 연동되는지 심층 검증 필요.
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `git-master`: Git 설정은 YAML 안에서 하므로 직접적 git 작업 아님

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (final)
  - **Blocks**: None (final task)
  - **Blocked By**: Tasks 2, 7

  **References**:

  **Pattern References**:
  - `src/main.py` (Task 7) - 파이프라인 진입점
  - `src/notifier.py:send_failure_notification` (Task 6) - 실패 알림 함수

  **API/Type References**:
  - GitHub Actions 컨텍스트 변수: `${{ secrets.* }}`, `${{ github.repository }}`, `${{ github.run_id }}`
  - `actions/checkout@v4` - `token` 파라미터로 push 권한 확보
  - `actions/setup-python@v5` - `cache: 'pip'`으로 의존성 캐싱

  **External References**:
  - GitHub Actions workflow 문법: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions
  - GitHub Actions schedule 트리거: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
  - actions/checkout: https://github.com/actions/checkout
  - actions/setup-python: https://github.com/actions/setup-python

  **WHY Each Reference Matters**:
  - `concurrency` 설정으로 동시 실행 방지가 핵심 (수동 + 크론 동시 실행 시 git push 충돌)
  - `permissions` 설정으로 GITHUB_TOKEN에 올바른 권한 부여 필수
  - `if: failure()` 조건으로 파이프라인 실패 시에만 알림 발송

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: GitHub Actions YAML 유효성 검증
    Tool: Bash (python)
    Steps:
      1. python -c "
         import yaml
         with open('.github/workflows/daily-digest.yml') as f:
             config = yaml.safe_load(f)
         print(f'Name: {config[\"name\"]}')
         print(f'Has schedule: {\"schedule\" in config[\"on\"]}')
         print(f'Has workflow_dispatch: {\"workflow_dispatch\" in config[\"on\"]}')
         print(f'Has concurrency: {\"concurrency\" in config}')
         print(f'Permissions: {config.get(\"permissions\", {})}')
         cron = config['on']['schedule'][0]['cron']
         print(f'Cron: {cron}')
         "
      2. Assert: Name == "InsightFlow Daily Digest"
      3. Assert: Has schedule == True
      4. Assert: Has workflow_dispatch == True
      5. Assert: Has concurrency == True
      6. Assert: Permissions에 contents: write, issues: write 포함
      7. Assert: Cron == "0 23 * * *"
    Expected Result: YAML이 올바르게 파싱되고 모든 필수 설정 포함
    Evidence: python 출력 캡처

  Scenario: 전체 모듈 import 성공
    Tool: Bash (python)
    Steps:
      1. python -c "
         from src.config import KEYWORDS, GEEKNEWS_RSS_URL
         from src.scraper import scrape_all, Article
         from src.ai_handler import filter_and_summarize
         from src.storage import load_seen_ids, save_seen_ids, filter_new_articles, save_daily_articles
         from src.notifier import send_digest, send_failure_notification
         print('All imports successful')
         "
      2. Assert: "All imports successful" 출력
    Expected Result: 모든 모듈이 에러 없이 import됨
    Evidence: python 출력 캡처

  Scenario: 전체 파일 구조 확인
    Tool: Bash
    Steps:
      1. test -f .github/workflows/daily-digest.yml && echo "WORKFLOW OK"
      2. test -f src/__init__.py && echo "INIT OK"
      3. test -f src/main.py && echo "MAIN OK"
      4. test -f src/scraper.py && echo "SCRAPER OK"
      5. test -f src/ai_handler.py && echo "AI OK"
      6. test -f src/storage.py && echo "STORAGE OK"
      7. test -f src/notifier.py && echo "NOTIFIER OK"
      8. test -f src/config.py && echo "CONFIG OK"
      9. test -f requirements.txt && echo "REQUIREMENTS OK"
      10. test -f .env.example && echo "ENV OK"
      11. test -f README.md && echo "README OK"
      12. test -d data && echo "DATA DIR OK"
    Expected Result: 모든 12개 항목 OK
    Evidence: 명령 출력 캡처

  Scenario: 전체 파이프라인 dry-run (최종 통합 테스트)
    Tool: Bash
    Preconditions: .env에 유효한 GEMINI_API_KEY 설정
    Steps:
      1. python src/main.py --dry-run 2>&1
      2. Assert: exit code 0
      3. Assert: 출력에 "Pipeline completed" 또는 "No new articles" 포함
      4. ls data/ 확인
      5. Assert: data/ 아래에 JSON 파일 또는 seen_ids.json 존재
    Expected Result: 전체 파이프라인이 로컬에서 에러 없이 완료됨
    Evidence: 전체 stdout/stderr + data/ 파일 목록 캡처
  ```

  **Commit**: YES
  - Message: `ci: add GitHub Actions daily digest workflow with failure notifications`
  - Files: `.github/workflows/daily-digest.yml`
  - Pre-commit: `python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-digest.yml')); print('VALID')"`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(config): add project setup with config module and dependencies` | requirements.txt, .env.example, src/__init__.py, src/config.py, data/.gitkeep | `python -c "from src.config import KEYWORDS; print('OK')"` |
| 2 | `docs: add README with architecture diagram and setup guide` | README.md | `test -f README.md` |
| 3 | `feat(scraper): add GeekNews Atom feed and HN API data collection` | src/scraper.py | `python -c "from src.scraper import scrape_all; print('OK')"` |
| 4 | `feat(ai): add Gemini batch summarization with keyword filtering` | src/ai_handler.py | `python -c "from src.ai_handler import filter_and_summarize; print('OK')"` |
| 5 | `feat(storage): add JSON storage, deduplication, and GitHub Issues creation` | src/storage.py | `python -c "from src.storage import load_seen_ids; print('OK')"` |
| 6 | `feat(notifier): add Telegram digest formatting with message chunking` | src/notifier.py | `python -c "from src.notifier import send_digest; print('OK')"` |
| 7 | `feat(main): add pipeline orchestrator with dry-run support` | src/main.py | `python src/main.py --dry-run` |
| 8 | `ci: add GitHub Actions daily digest workflow with failure notifications` | .github/workflows/daily-digest.yml | `python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-digest.yml')); print('VALID')"` |

---

## Success Criteria

### Verification Commands
```bash
# 전체 모듈 import 확인
python -c "from src.config import *; from src.scraper import *; from src.ai_handler import *; from src.storage import *; from src.notifier import *; print('ALL IMPORTS OK')"

# dry-run 전체 파이프라인
python src/main.py --dry-run  # Expected: exit code 0, "Pipeline completed" in output

# 중복 방지 확인 (두 번 실행)
python src/main.py --dry-run && python src/main.py --dry-run  # Expected: 두 번째 실행에서 새 기사 0개

# YAML 유효성
python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-digest.yml')); print('VALID')"

# 파일 구조 완전성
ls -la src/main.py src/scraper.py src/ai_handler.py src/storage.py src/notifier.py src/config.py .github/workflows/daily-digest.yml README.md requirements.txt .env.example
```

### Final Checklist
- [ ] All "Must Have" present (11개 항목)
- [ ] All "Must NOT Have" absent (12개 가드레일)
- [ ] 전체 파이프라인 `--dry-run` 성공
- [ ] GitHub Actions YAML 유효
- [ ] README에 아키텍처 다이어그램 + 로컬 테스트 가이드 포함
- [ ] 텔레그램 테스트 메시지 발송 성공
- [ ] 중복 실행 시 데이터 중복 없음
- [ ] Gemini API 호출 횟수 < 20 per run (배칭 효과)
