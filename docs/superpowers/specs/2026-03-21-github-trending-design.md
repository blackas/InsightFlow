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
- 기존 `USER_AGENT` 헤더 재사용, `timeout=15` (기존 `fetch_tldr_ai()`와 동일)
- HTTP 200이지만 파싱 결과가 0개인 경우: 별도 경고 로그 (`logger.warning`) — 셀렉터 깨짐 감지용
- 네트워크 에러 시 빈 리스트 반환 + `logger.exception`
- **`scrape_all()`은 수정하지 않음** — Trending은 Article 파이프라인과 독립적으로 `main.py`에서 별도 호출

### 2. `src/config.py`

- `GITHUB_TRENDING_URL = "https://github.com/trending"`
- `GITHUB_TRENDING_COUNT = 10`

### 3. `src/notifier.py`

- `_format_trending(repos: list[TrendingRepo]) -> str` 함수 추가
- Telegram MarkdownV2 포맷으로 Trending 섹션 생성
- 리포 이름, 설명 등 모든 텍스트에 `_escape_md()` 적용
- `language`가 `None`이면 언어 표시 생략, 설명만 표시
- `trending_repos` 파라미터를 `format_digest()`와 `send_digest()` 양쪽에 추가
- Trending 섹션 위치: Model Updates 뒤 (다이제스트 최하단)
- **`send_digest()` 빈 articles 가드 수정:** `articles`가 비어있어도 `trending_repos`가 있으면 전송 진행

### 4. `src/main.py`

- Step 7.7로 Trending 수집 단계 추가 (Model Dashboard 7.6 이후, Telegram 8 이전)
- `fetch_github_trending()` 호출 → 결과를 `send_digest()`의 `trending_repos`에 전달
- 에러 처리: non-fatal (`try/except`로 감싸고 `logger.exception`, 파이프라인 계속)

### 5. `tests/`

- `tests/test_scraper_behavior.py` — `fetch_github_trending()` 테스트
  - HTML 파싱 정상 동작
  - 네트워크 에러 시 빈 리스트 반환
  - count 파라미터 동작
  - HTTP 200 + 파싱 결과 0개 시 경고 로그
- `tests/test_notifier.py` — `_format_trending()` 포매팅 테스트
  - 정상 리포 목록 포매팅
  - 빈 리스트 처리
  - MarkdownV2 특수문자 이스케이프 (리포 이름의 `.`, `-`, `_` 등)
  - `language`가 `None`인 경우
- `tests/test_main.py` — 파이프라인 통합 테스트
  - Trending 수집 실패 시 파이프라인 계속 동작
  - articles 비어있고 trending만 있을 때 전송 동작

## Telegram 메시지 형식

```
🔥 GitHub Trending (Daily)

1. owner/repo ⭐ 1,234 (+567 today)
   Python | 리포지토리 설명 텍스트

2. owner/repo ⭐ 890 (+234 today)
   Rust | 설명 ...

3. owner/repo ⭐ 456 (+123 today)
   리포지토리 설명 (language가 None인 경우)
```

## 에러 처리

- 네트워크 실패: 빈 리스트 반환, `logger.exception`, 파이프라인 계속 (model_tracker와 동일한 non-fatal 패턴)
- HTTP 200 + 파싱 결과 0개: `logger.warning("GitHub Trending page returned 200 but no repos parsed — selectors may be broken")`, 빈 리스트 반환
- Trending 결과가 비어있으면: Telegram 섹션 자체를 생략

## 제외 사항

- Notion 동기화: 제외 (기사가 아니므로 articles DB 스키마와 불일치)
- seen_ids 중복 제거: 제외 (매일 새로운 Trending)
- GitHub Issues / 블로그: 제외 (Telegram 전용)
- Gemini 요약: 제외 (리포 description으로 충분)
