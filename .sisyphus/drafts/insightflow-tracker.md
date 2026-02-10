# Draft: InsightFlow - AI Tech Tracking App

## Requirements (confirmed)

### 인프라 결정
- **서버**: 없음 (GitHub Actions 전용, VPS 미사용)
- **스케줄링**: GitHub Actions cron - 매일 오전 8시 KST (UTC 23:00 전날)
- **시크릿 관리**: GitHub Secrets (Gemini API Key, Telegram Bot Token)
- **Python 버전**: 3.11

### 기능적 결정
- **데이터 소스**: GeekNews RSS + Hacker News API (2개, 확장 가능하게 설계)
- **LLM**: Gemini만 사용 (Google Gemini API)
- **필터링 전략**: 키워드 화이트리스트로 1차 필터 → Gemini로 2차 관련성 판단 (하이브리드)
- **데이터 저장**: JSON 파일 (전체 데이터) + GitHub Issues (주요 기사만)
- **알림**: 텔레그램 봇 - 일일 단일 메시지 형태
- **중복 방지**: 필요 (사용자 명시적 요청)
- **실패 알림**: 필요 (사용자 명시적 요청)

### 모듈 구조 (사용자 요청)
- `main.py` - 메인 오케스트레이터
- `scraper.py` - RSS/API 데이터 수집
- `ai_handler.py` - Gemini 기반 요약/필터링
- 추가 모듈은 설계 시 결정

### 사용자 요청 산출물
1. 시스템 아키텍처 설계도 (Mermaid 차트)
2. `.github/workflows/main.yml` 상세 설정
3. 모듈화된 Python 코드
4. 로컬 테스트 환경 구성 가이드
5. 실패 알림 메커니즘
6. 중복 수집 방지 로직

## Technical Decisions
- **Gemini 선택 이유**: 사용자 선호. 무료 티어 활용 가능 (분당 15회)
- **하이브리드 필터링**: 키워드로 비용 절감 + LLM으로 정확도 보장
- **JSON + Issues 병행**: JSON으로 전체 이력, Issues로 주요 기사 가시성

## Resolved Questions
- **Gemini 모델**: gemini-2.0-flash (무료 티어: 분당 15회, 일 1,500회 - 충분)
- **관심 키워드**: 풀스택 개발자 + 인프라 중심 (AI, LLM, React, TypeScript, Rust, Go, Docker, K8s, DevOps, 데이터베이스, 클라우드, 마이크로서비스, API)
- **텔레그램**: 봇 사용 (개인 채팅 또는 채널 - 봇 토큰 + chat_id로 발송)
- **로컬 테스트**: .env 파일로 환경변수 관리 (python-dotenv)

## Research Findings

### Gemini API 무료 티어 (2026년 2월 기준 - 중요!)
- **2025년 12월 Google이 무료 티어 대폭 축소함**
- gemini-2.0-flash: RPM 15, **RPD 1,500** (하루 1,500건 요청)
- gemini-2.5-flash: RPM 15, **RPD 500**
- gemini-2.5-pro: RPM 5, **RPD 25** (사실상 무료로는 사용 불가)
- **결론**: gemini-2.0-flash 선택이 최적. 하루 기사 수집 20~50건이면 여유 있음
- Rate limit 에러(429) 대비 재시도 로직 필수

### GitHub Actions Cron 스케줄링
- UTC 기준으로 cron 설정 (KST 08:00 = UTC 23:00 전날)
- `cron: '0 23 * * *'` → 매일 한국시간 오전 8시
- `workflow_dispatch` 추가하면 수동 트리거도 가능
- 실행 시간 제한: 6시간 (충분)
- 주의: 스케줄 정확도 ±5~15분 편차 발생 가능 (GitHub 부하에 따라)

### 데이터 저장/커밋 패턴
- `aastroza/rss-feeds-scraper` 프로젝트: GitHub Actions에서 JSON 파일로 RSS 저장하고 자동 커밋하는 패턴 사용
- GitHub Actions 내에서 `git add && git commit && git push` 가능
- `actions/checkout@v4` + `actions/setup-python@v6` 조합

### GeekNews RSS
- GeekNews MCP 서버 존재 (BeautifulSoup 기반 스크래핑)
- RSS URL: `https://news.hada.io/rss` (확인 필요)
- Hacker News API: `https://hacker-news.firebaseio.com/v0/` (공식 API)

### 실패 알림 메커니즘
- GitHub Actions 자체 이메일 알림 (기본 제공)
- 텔레그램으로도 실패 알림 발송 가능 (workflow의 `if: failure()` 조건)

## Remaining Open Questions
- GitHub Issues 라벨 구조? → 기본값으로 설계 (소스별 + 카테고리별)

## Scope Boundaries
- INCLUDE: RSS 수집, LLM 요약, 텔레그램 발송, GitHub Actions CI/CD, 데이터 저장, 중복방지, 실패알림
- EXCLUDE: 웹 UI, 사용자 인증, 실시간 모니터링, 다국어 지원, Reddit/기타 소스
