# GitHub Trending 리포지토리 수집 기능 설계

## 개요

GitHub Trending (daily, 전체 언어) 페이지에서 상위 10개 리포지토리를 스크래핑하여 Telegram 다이제스트에 별도 섹션으로 전달하는 기능.

## 요구사항

- **소스:** `https://github.com/trending` (daily, 전체 언어)
- **수집 개수:** 상위 10개
- **통합 방식:** 기존 Article 파이프라인과 독립, Telegram 전용 별도 섹션
- **필터링:** 키워드 필터 / Gemini 요약 적용 안 함 (전체 노출)
- **제외 대상:** Notion 동기화, seen_ids 중복 제거, GitHub Issues, 블로그 — 모두 제외

## 기술 선택

HTML 스크래핑 (`requests` + `BeautifulSoup`). 프로젝트에 이미 있는 의존성만 사용. TLDR AI 스크래핑과 동일한 패턴.

## 데이터 모델

```python
@dataclass
class TrendingRepo:
    name: str            # "owner/repo"
    url: str             # https://github.com/owner/repo
    description: str
    language: str | None
    stars: int           # 총 스타 수
    today_stars: int     # 오늘의 스타 증가량
    forks: int
```

## 변경 파일

### 1. `src/scraper.py`

- `TrendingRepo` 데이터클래스 추가
- `fetch_github_trending(count: int = 10) -> list[TrendingRepo]` 함수 추가
- `github.com/trending` 페이지를 `requests` + `BeautifulSoup`으로 파싱
- 스크래핑 실패 시 빈 리스트 반환 + 로그

### 2. `src/config.py`

- `GITHUB_TRENDING_URL = "https://github.com/trending"`
- `GITHUB_TRENDING_COUNT = 10`

### 3. `src/notifier.py`

- `_format_trending(repos: list[TrendingRepo]) -> str` 함수 추가
- Telegram MarkdownV2 포맷으로 Trending 섹션 생성
- `send_digest()`에 `trending_repos` 파라미터 추가, 다이제스트 끝에 Trending 섹션 첨부

### 4. `src/main.py`

- 파이프라인에 Trending 수집 단계 추가 (Step 7 Model Tracker 부근)
- `fetch_github_trending()` 호출 → 결과를 `send_digest()`에 전달
- 에러 처리: non-fatal (로그만 남기고 계속)

### 5. `tests/`

- `tests/test_scraper.py` 또는 `tests/test_scraper_behavior.py` — `fetch_github_trending()` 테스트
  - HTML 파싱 정상 동작
  - 네트워크 에러 시 빈 리스트 반환
  - count 파라미터 동작
- `tests/test_notifier.py` — `_format_trending()` 포매팅 테스트
  - 정상 리포 목록 포매팅
  - 빈 리스트 처리
  - MarkdownV2 특수문자 이스케이프
- `tests/test_main.py` — 파이프라인 통합 테스트
  - Trending 수집 실패 시 파이프라인 계속 동작

## Telegram 메시지 형식

```
🔥 GitHub Trending (Daily)

1. owner/repo ⭐ 1,234 (+567 today)
   Python | 리포지토리 설명 텍스트

2. owner/repo ⭐ 890 (+234 today)
   Rust | 설명 ...
```

## 에러 처리

- 스크래핑 실패: 빈 리스트 반환, 로그 남기고 파이프라인 계속 (model_tracker와 동일한 non-fatal 패턴)
- Trending 결과가 비어있으면: Telegram 섹션 자체를 생략

## 제외 사항

- Notion 동기화: 제외 (기사가 아니므로 articles DB 스키마와 불일치)
- seen_ids 중복 제거: 제외 (매일 새로운 Trending)
- GitHub Issues / 블로그: 제외 (Telegram 전용)
- Gemini 요약: 제외 (리포 description으로 충분)
